"""
Temporal Workflows for Claude Code orchestration.

Workflows provide multi-stage orchestration with:
- Human-in-the-loop approval gates
- Automatic testing and validation
- Cost tracking
- Snapshot-based rollback
"""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from .models import (
        ClaudeCodeInput,
        ClaudeCodeResult,
        TestResult,
        CostEstimate,
        WorkflowState,
        NotificationParams,
        MetricsData,
        FeatureResult,
    )
    from .activities import (
        execute_claude_code,
        run_tests,
        estimate_cost,
        create_snapshot,
        notify_developer,
        capture_metrics,
        restore_snapshot,
    )
    from .stages import (
        DevelopmentStage,
        StageConfig,
        create_stage_config,
    )
    from .constants import (
        MAX_TOKENS_BEFORE_COOLDOWN,
        COOLDOWN_SECONDS,
        RETRY_INITIAL_INTERVAL_SECONDS,
        RETRY_BACKOFF_COEFFICIENT,
        RETRY_MAX_ATTEMPTS,
        RETRY_MAX_INTERVAL_SECONDS,
        APPROVAL_TIMEOUT_HOURS,
        DEFAULT_MAX_ITERATIONS,
        ITERATION_BACKOFF_BASE_SECONDS,
        ITERATION_BACKOFF_MAX_SECONDS,
    )


# Default retry policy for activities
DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=RETRY_INITIAL_INTERVAL_SECONDS),
    backoff_coefficient=RETRY_BACKOFF_COEFFICIENT,
    maximum_attempts=RETRY_MAX_ATTEMPTS,
    maximum_interval=timedelta(seconds=RETRY_MAX_INTERVAL_SECONDS),
)


@workflow.defn
class DevelopLLMWrapperWorkflow:
    """
    Main Workflow: Develop LLM Wrapper with Full Observability.

    Features:
    - Multi-stage development orchestration
    - Cost tracking in real-time
    - Human-in-the-loop approval gates
    - Automatic rollback on test failure
    - Complete audit trail
    """

    def __init__(self):
        self._state = WorkflowState()
        self._approved: Optional[bool] = None

    @workflow.signal
    async def approve(self) -> None:
        """Signal to approve current stage."""
        self._approved = True

    @workflow.signal
    async def reject(self) -> None:
        """Signal to reject current stage."""
        self._approved = False

    @workflow.query
    def get_state(self) -> dict:
        """Query current workflow state."""
        return {
            "current_stage": self._state.current_stage,
            "total_tokens_used": self._state.total_tokens_used,
            "total_cost": self._state.total_cost,
            "tests_passed_count": self._state.tests_passed_count,
            "snapshots": self._state.snapshots,
        }

    async def _estimate_stage_cost(self, stage: DevelopmentStage) -> CostEstimate:
        """Pre-execution cost estimation for a stage."""
        complexity = "high" if stage.critical_path else "medium"
        return await workflow.execute_activity(
            estimate_cost,
            args=[stage.prompt, complexity],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

    async def _create_stage_snapshot(self, project_path: str) -> str:
        """Create snapshot before critical operations."""
        snapshot_id = await workflow.execute_activity(
            create_snapshot,
            args=[project_path],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=DEFAULT_RETRY_POLICY,
        )
        self._state.snapshots.append(snapshot_id)
        return snapshot_id

    async def _execute_stage(
        self, stage: DevelopmentStage, project_path: str
    ) -> ClaudeCodeResult:
        """Execute Claude Code for a stage."""
        return await workflow.execute_activity(
            execute_claude_code,
            args=[ClaudeCodeInput(
                prompt=stage.prompt,
                working_directory=project_path,
                max_tokens=stage.max_tokens,
                temperature=stage.temperature,
            )],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

    async def _validate_stage(
        self, stage: DevelopmentStage, project_path: str
    ) -> Optional[TestResult]:
        """Validate stage by running tests."""
        if stage.skip_tests:
            return None

        return await workflow.execute_activity(
            run_tests,
            args=[project_path],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

    async def _handle_test_failure(
        self, stage: DevelopmentStage, project_path: str
    ) -> None:
        """Handle test failure with rollback for critical stages."""
        workflow.logger.error(f"Tests failed in {stage.name}")

        if stage.critical_path and self._state.snapshots:
            last_snapshot = self._state.snapshots[-1]
            workflow.logger.info(f"Rolling back to snapshot: {last_snapshot}")
            await workflow.execute_activity(
                restore_snapshot,
                args=[project_path, last_snapshot],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=DEFAULT_RETRY_POLICY,
            )
            raise ApplicationError(
                f"Critical stage {stage.name} failed tests",
                non_retryable=True,
            )

    async def _wait_for_approval(self, stage: DevelopmentStage) -> None:
        """Wait for human approval on a stage."""
        workflow.logger.info(f"Waiting for approval on stage: {stage.name}")

        try:
            await workflow.wait_condition(
                lambda: self._approved is not None,
                timeout=timedelta(hours=APPROVAL_TIMEOUT_HOURS),
            )
        except asyncio.TimeoutError:
            raise ApplicationError(
                f"Approval timeout for stage {stage.name}",
                non_retryable=True,
            )

        if not self._approved:
            raise ApplicationError(
                f"Stage {stage.name} rejected by developer",
                non_retryable=True,
            )

        self._approved = None  # Reset for next approval
        workflow.logger.info(f"Stage {stage.name} approved, continuing...")

    async def _notify_for_approval(
        self, stage: DevelopmentStage, result: ClaudeCodeResult
    ) -> None:
        """Send notification for stage approval."""
        await workflow.execute_activity(
            notify_developer,
            args=[NotificationParams(
                stage=stage.name,
                message=f"Stage '{stage.name}' complete. Review required.",
                files_changed=result.files_modified,
                diff_url=result.diff_url,
            )],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

    async def _capture_stage_metrics(
        self,
        stage: DevelopmentStage,
        result: ClaudeCodeResult,
        test_result: Optional[TestResult],
    ) -> None:
        """Capture metrics after stage completion."""
        await workflow.execute_activity(
            capture_metrics,
            args=[MetricsData(
                stage=stage.name,
                tokens_used=result.tokens_used,
                cost=result.cost,
                duration_ms=result.duration_ms,
                files_modified=len(result.files_modified),
                lines_added=result.lines_added,
                lines_removed=result.lines_removed,
                tests_pass=stage.skip_tests or (test_result and test_result.success),
            )],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

    async def _apply_rate_limiting(self) -> None:
        """Apply rate limiting cooldown if needed."""
        if self._state.total_tokens_used > MAX_TOKENS_BEFORE_COOLDOWN:
            workflow.logger.info(
                f"High token usage, cooling down for {COOLDOWN_SECONDS}s..."
            )
            await asyncio.sleep(COOLDOWN_SECONDS)

    async def _process_stage(
        self, stage: DevelopmentStage, project_path: str
    ) -> None:
        """Process a single development stage."""
        self._state.current_stage = stage.name
        workflow.logger.info(f"=== Starting Stage: {stage.name} ===")

        # Pre-execution cost estimation
        cost_estimate = await self._estimate_stage_cost(stage)
        workflow.logger.info(f"Estimated cost: ${cost_estimate.estimated:.4f}")

        # Create snapshot before critical operations
        if stage.critical_path:
            snapshot_id = await self._create_stage_snapshot(project_path)
            workflow.logger.info(f"Created snapshot: {snapshot_id}")

        # Execute Claude Code
        result = await self._execute_stage(stage, project_path)
        self._state.total_tokens_used += result.tokens_used
        self._state.total_cost += result.cost

        # Validate stage
        test_result = await self._validate_stage(stage, project_path)
        if test_result and not test_result.success:
            await self._handle_test_failure(stage, project_path)
        elif test_result:
            self._state.tests_passed_count += 1

        # Human-in-the-loop approval
        if stage.requires_approval:
            await self._notify_for_approval(stage, result)
            await self._wait_for_approval(stage)

        # Capture metrics
        await self._capture_stage_metrics(stage, result, test_result)

        # Rate limiting
        await self._apply_rate_limiting()

    @workflow.run
    async def run(self, project_path: str, features: list[str]) -> dict:
        """
        Execute the full LLM wrapper development workflow.

        Args:
            project_path: Path to the project directory
            features: List of features to implement

        Returns:
            Final workflow state as dict
        """
        # Get stage configuration
        stage_config = create_stage_config(workflow_type="llm-wrapper")
        stages = stage_config.get_stages(project_path=project_path)

        try:
            # Process all stages
            for stage in stages:
                await self._process_stage(stage, project_path)

            # Final validation
            workflow.logger.info("=== Final Validation ===")
            final_tests = await workflow.execute_activity(
                run_tests,
                args=[project_path],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=DEFAULT_RETRY_POLICY,
            )

            if not final_tests.success:
                raise ApplicationError("Final test suite failed", non_retryable=True)

            workflow.logger.info("=== Development Complete ===")
            workflow.logger.info(
                f"Total tokens used: {self._state.total_tokens_used}"
            )
            workflow.logger.info(f"Total cost: ${self._state.total_cost:.2f}")
            workflow.logger.info(
                f"Tests passed: {self._state.tests_passed_count}/{len(stages) - 1}"
            )

            return self.get_state()

        except Exception as e:
            # Capture error metrics
            await workflow.execute_activity(
                capture_metrics,
                args=[MetricsData(
                    stage=self._state.current_stage,
                    tokens_used=0,
                    cost=0,
                    duration_ms=0,
                    error=str(e),
                )],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=DEFAULT_RETRY_POLICY,
            )
            raise


@workflow.defn
class IterativeRefinementWorkflow:
    """
    Iterative Refinement Workflow.

    Handles multiple iterations with feedback loops and exponential backoff.
    """

    async def _run_iteration(
        self, project_path: str, issue: str, iteration: int
    ) -> tuple[ClaudeCodeResult, TestResult]:
        """Run a single iteration of the fix."""
        # Create snapshot before each iteration
        await workflow.execute_activity(
            create_snapshot,
            args=[project_path],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        # Ask Claude to fix the issue
        result = await workflow.execute_activity(
            execute_claude_code,
            args=[ClaudeCodeInput(
                prompt=f"Fix this issue: {issue}. Previous attempts: {iteration - 1}. Run tests after fixing.",
                working_directory=project_path,
                max_tokens=4000,
                temperature=0.3,
            )],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        # Validate the fix
        test_result = await workflow.execute_activity(
            run_tests,
            args=[project_path],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        return result, test_result

    async def _capture_iteration_metrics(
        self,
        iteration: int,
        result: ClaudeCodeResult,
        tests_passing: bool,
    ) -> None:
        """Capture metrics for an iteration."""
        await workflow.execute_activity(
            capture_metrics,
            args=[MetricsData(
                stage=f"iteration-{iteration}",
                tokens_used=result.tokens_used,
                cost=result.cost,
                duration_ms=result.duration_ms,
                files_modified=len(result.files_modified),
                tests_pass=tests_passing,
            )],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

    @workflow.run
    async def run(
        self,
        project_path: str,
        issue: str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> str:
        """
        Iteratively fix an issue until tests pass.

        Args:
            project_path: Path to the project
            issue: Description of the issue to fix
            max_iterations: Maximum retry attempts

        Returns:
            Summary of resolution
        """
        iteration = 0
        tests_passing = False

        while iteration < max_iterations and not tests_passing:
            iteration += 1
            workflow.logger.info(f"=== Iteration {iteration} ===")

            result, test_result = await self._run_iteration(
                project_path, issue, iteration
            )
            tests_passing = test_result.success

            await self._capture_iteration_metrics(iteration, result, tests_passing)

            if not tests_passing:
                workflow.logger.info(
                    f"Tests still failing. Retrying... ({iteration}/{max_iterations})"
                )
                # Exponential backoff
                backoff_seconds = min(
                    iteration * ITERATION_BACKOFF_BASE_SECONDS,
                    ITERATION_BACKOFF_MAX_SECONDS,
                )
                await asyncio.sleep(backoff_seconds)

        if not tests_passing:
            raise ApplicationError(
                f"Failed to fix issue after {max_iterations} iterations",
                non_retryable=True,
            )

        return f"Issue resolved in {iteration} iteration(s)"


@workflow.defn
class ParallelFeatureDevelopmentWorkflow:
    """
    Parallel Feature Development Workflow.

    Develops multiple features concurrently with isolated contexts.
    """

    async def _develop_feature(
        self, feature: str, index: int, project_path: str
    ) -> FeatureResult:
        """Develop a single feature on its own branch."""
        branch_name = f"feature-{index}-{feature.replace(' ', '-').lower()}"

        # Create feature branch
        await workflow.execute_activity(
            execute_claude_code,
            args=[ClaudeCodeInput(
                prompt=f"Create git branch {branch_name} and switch to it",
                working_directory=project_path,
                max_tokens=100,
                temperature=0.1,
            )],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        # Develop feature
        result = await workflow.execute_activity(
            execute_claude_code,
            args=[ClaudeCodeInput(
                prompt=f"Implement feature: {feature}. Include tests.",
                working_directory=project_path,
                max_tokens=6000,
                temperature=0.3,
            )],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        # Run tests
        test_result = await workflow.execute_activity(
            run_tests,
            args=[project_path],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        # Capture metrics
        await workflow.execute_activity(
            capture_metrics,
            args=[MetricsData(
                stage=f"feature-{feature}",
                tokens_used=result.tokens_used,
                cost=result.cost,
                duration_ms=result.duration_ms,
                files_modified=len(result.files_modified),
                tests_pass=test_result.success,
            )],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=DEFAULT_RETRY_POLICY,
        )

        return FeatureResult(
            feature=feature,
            branch=branch_name,
            success=test_result.success,
            tokens_used=result.tokens_used,
            test_results=test_result,
        )

    @workflow.run
    async def run(self, project_path: str, features: list[str]) -> list[dict]:
        """
        Develop multiple features in parallel.

        Args:
            project_path: Path to the project
            features: List of features to implement

        Returns:
            List of feature results
        """
        # Develop all features concurrently
        tasks = [
            self._develop_feature(f, i, project_path)
            for i, f in enumerate(features)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        feature_results = []
        for r in results:
            if isinstance(r, Exception):
                workflow.logger.error(f"Feature failed: {r}")
            else:
                feature_results.append({
                    "feature": r.feature,
                    "branch": r.branch,
                    "success": r.success,
                    "tokens_used": r.tokens_used,
                })

        workflow.logger.info("=== Parallel Development Results ===")
        for r in feature_results:
            status = "OK" if r["success"] else "FAILED"
            workflow.logger.info(f"{r['feature']}: {status} ({r['branch']})")

        return feature_results
