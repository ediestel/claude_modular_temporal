"""
Temporal Activities for Claude Code Integration.

These are the actual operations that interact with Claude Code CLI.
Each activity captures telemetry for observability.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from temporalio import activity

from .models import (
    ClaudeCodeInput,
    ClaudeCodeResult,
    TestResult,
    CostEstimate,
    NotificationParams,
    MetricsData,
)
from .config import get_config
from .constants import (
    CHARS_PER_TOKEN,
    COMPLEXITY_MULTIPLIERS,
    MODEL_PRICING,
    DEFAULT_MODEL,
)
from .git_utils import GitOperations
from .notification import get_notification_service
from .test_runner import get_test_runner


def estimate_tokens(text: str) -> int:
    """Estimate token count from text."""
    return len(text) // CHARS_PER_TOKEN


def calculate_cost(tokens: int, model: str = DEFAULT_MODEL) -> float:
    """Calculate cost based on token usage and model pricing."""
    rates = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    # Assume 50/50 split input/output for simplicity
    return (tokens / 1000) * ((rates["input"] + rates["output"]) / 2)


def _validate_path(path: str) -> Path:
    """
    Validate that a path exists.

    Args:
        path: Path to validate

    Returns:
        Path object

    Raises:
        ValueError: If path doesn't exist
    """
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Path does not exist: {path}")
    return p


@activity.defn
async def execute_claude_code(params: ClaudeCodeInput) -> ClaudeCodeResult:
    """
    Execute Claude Code with detailed telemetry.

    This activity runs the Claude CLI and captures all execution metadata
    for observability and cost tracking.
    """
    start_time = time.time()
    config = get_config()

    activity.logger.info(f"Executing Claude Code in {params.working_directory}")
    activity.logger.info(f"Prompt: {params.prompt[:100]}...")

    # Validate working directory
    _validate_path(params.working_directory)

    # Initialize git operations
    git = GitOperations(params.working_directory)

    # Store git state before changes
    before_status = await git.get_status()

    try:
        # Execute Claude Code CLI
        # Using --print flag for non-interactive output
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            params.prompt,
            cwd=params.working_directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "CLAUDE_MAX_TOKENS": str(params.max_tokens),
            },
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=config.claude.timeout_seconds,
        )

        output = stdout.decode() if stdout else stderr.decode()

        # Get git changes after execution
        after_status = await git.get_status()
        files_modified = after_status.files_changed

        # Get diff stats
        diff_stats = await git.get_diff_stats()

        # Estimate tokens and cost
        tokens_used = estimate_tokens(params.prompt + output)
        cost = calculate_cost(tokens_used)

        duration_ms = int((time.time() - start_time) * 1000)

        result = ClaudeCodeResult(
            output=output,
            tokens_used=tokens_used,
            cost=cost,
            duration_ms=duration_ms,
            files_modified=files_modified,
            lines_added=diff_stats.lines_added,
            lines_removed=diff_stats.lines_removed,
        )

        activity.logger.info(f"Completed in {duration_ms}ms")
        activity.logger.info(f"Tokens: {tokens_used}, Cost: ${cost:.4f}")
        activity.logger.info(f"Files modified: {len(files_modified)}")

        return result

    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Claude Code execution timed out after {config.claude.timeout_seconds}s"
        )
    except Exception as e:
        activity.logger.error(f"Failed: {e}")
        raise RuntimeError(f"Claude Code execution failed: {e}")


@activity.defn
async def run_tests(project_path: str) -> TestResult:
    """
    Run test suite with detailed results.

    Automatically detects and uses the appropriate test framework.
    """
    activity.logger.info(f"Running tests in {project_path}")

    # Validate path
    _validate_path(project_path)

    # Get auto-detecting test runner
    runner = get_test_runner()

    # Run tests
    result = await runner.run(project_path)

    activity.logger.info(f"Tests completed in {result.duration_ms}ms")
    activity.logger.info(f"Passed: {result.passed}/{result.total_tests}")

    return result


@activity.defn
async def estimate_cost(prompt: str, complexity: str = "medium") -> CostEstimate:
    """
    Estimate cost before execution for budget control.
    """
    # Base token estimate from prompt
    prompt_tokens = estimate_tokens(prompt)

    # Estimate completion tokens based on complexity
    multiplier = COMPLEXITY_MULTIPLIERS.get(complexity, COMPLEXITY_MULTIPLIERS["medium"])
    completion_tokens = prompt_tokens * multiplier

    total_tokens = prompt_tokens + completion_tokens
    cost = calculate_cost(total_tokens)

    return CostEstimate(
        estimated=cost,
        model=DEFAULT_MODEL,
        tokens_estimate=total_tokens,
    )


@activity.defn
async def create_snapshot(project_path: str) -> str:
    """
    Create project snapshot for rollback capability.

    Uses git commits as snapshots for safe experimentation.
    """
    snapshot_id = f"snapshot-{int(time.time())}"
    activity.logger.info(f"Creating snapshot: {snapshot_id}")

    try:
        # Validate path
        _validate_path(project_path)

        git = GitOperations(project_path)
        result = await git.create_snapshot(snapshot_id)

        if result.success:
            activity.logger.info(f"Snapshot created: {snapshot_id}")
        else:
            activity.logger.warning(f"Snapshot creation issue: {result.error}")

        return snapshot_id

    except Exception as e:
        activity.logger.warning(f"Failed to create snapshot: {e}")
        return snapshot_id  # Return ID anyway for tracking


@activity.defn
async def notify_developer(params: NotificationParams) -> None:
    """
    Notify developer with context for human-in-the-loop approval.

    Uses configurable notification service (console, Slack, webhook, etc.)
    """
    activity.logger.info(f"Notifying developer...")
    activity.logger.info(f"Stage: {params.stage}")
    activity.logger.info(f"Message: {params.message}")
    activity.logger.info(f"Files changed: {', '.join(params.files_changed)}")

    # Get notification service from config
    config = get_config()
    notification_config = {
        "type": config.notification.type,
        "webhook_url": config.notification.slack_webhook_url,
        "channel": config.notification.slack_channel,
        "url": config.notification.webhook_url,
        "headers": config.notification.webhook_headers,
    }

    service = get_notification_service(notification_config)
    success = await service.send(params)

    if success:
        activity.logger.info(f"Notification sent via {service.get_name()}")
    else:
        activity.logger.warning(f"Failed to send notification via {service.get_name()}")


@activity.defn
async def capture_metrics(data: MetricsData) -> None:
    """
    Capture metrics to monitoring system for complete observability.

    Writes metrics to file for later analysis.
    """
    config = get_config()

    metrics = {
        "stage": data.stage,
        "tokens_used": data.tokens_used,
        "cost": data.cost,
        "duration_ms": data.duration_ms,
        "files_modified": data.files_modified,
        "lines_added": data.lines_added,
        "lines_removed": data.lines_removed,
        "tests_pass": data.tests_pass,
        "error": data.error,
        "timestamp": data.timestamp,
    }

    activity.logger.info(f"Capturing metrics: {metrics}")

    # Write to metrics file asynchronously
    try:
        metrics_path = Path(config.metrics_file)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)

        # Use async file writing via run_in_executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _write_metrics,
            metrics_path,
            metrics,
        )

        activity.logger.info("Metrics captured")
    except Exception as e:
        activity.logger.warning(f"Failed to write metrics: {e}")


def _write_metrics(path: Path, metrics: dict) -> None:
    """Synchronous helper for writing metrics to file."""
    with open(path, "a") as f:
        f.write(json.dumps(metrics) + "\n")


@activity.defn
async def restore_snapshot(project_path: str, snapshot_id: str) -> bool:
    """
    Restore project to a previous snapshot.
    """
    activity.logger.info(f"Restoring snapshot: {snapshot_id}")

    try:
        # Validate path
        _validate_path(project_path)

        git = GitOperations(project_path)
        result = await git.restore_snapshot(snapshot_id)

        if result.success:
            activity.logger.info(f"Restored to snapshot: {snapshot_id}")
            return True
        else:
            activity.logger.error(f"Failed to restore: {result.error}")
            return False

    except Exception as e:
        activity.logger.error(f"Failed to restore snapshot: {e}")
        return False
