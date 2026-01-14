"""
Temporal Client for Claude Code workflows.

CLI interface for starting and managing workflows.

Usage:
    python -m claude_temporal.client start [project_path]
    python -m claude_temporal.client approve <workflow_id>
    python -m claude_temporal.client reject <workflow_id>
    python -m claude_temporal.client status <workflow_id>
"""

import argparse
import asyncio
import logging
import sys
import time
from typing import Any, Callable, TypeVar

from temporalio.client import Client, WorkflowHandle

from .config import get_config
from .constants import (
    WORKFLOW_ID_PREFIX_DEVELOP,
    WORKFLOW_ID_PREFIX_ITERATIVE,
    WORKFLOW_ID_PREFIX_PARALLEL,
)
from .workflows import (
    DevelopLLMWrapperWorkflow,
    IterativeRefinementWorkflow,
    ParallelFeatureDevelopmentWorkflow,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


T = TypeVar("T")


async def get_client() -> Client:
    """Get a connected Temporal client."""
    config = get_config()
    return await Client.connect(
        config.temporal.address,
        namespace=config.temporal.namespace,
    )


def generate_workflow_id(prefix: str) -> str:
    """Generate a unique workflow ID with timestamp."""
    return f"{prefix}-{int(time.time() * 1000)}"


async def start_workflow_helper(
    workflow_run: Callable[..., T],
    args: list[Any],
    workflow_id: str,
    description: str,
) -> WorkflowHandle:
    """
    Helper function to start a workflow with common boilerplate.

    Args:
        workflow_run: The workflow run method
        args: Arguments to pass to the workflow
        workflow_id: Unique workflow ID
        description: Human-readable description for logging

    Returns:
        WorkflowHandle for the started workflow
    """
    config = get_config()

    logger.info("Connecting to Temporal...")
    client = await get_client()

    logger.info(f"Starting {description}...")
    logger.info("")

    handle = await client.start_workflow(
        workflow_run,
        args=args,
        id=workflow_id,
        task_queue=config.temporal.task_queue,
    )

    print(f"Workflow started!")
    print(f"Workflow ID: {handle.id}")
    print("")
    print(
        f"View in Temporal UI: "
        f"{config.temporal.ui_base_url}/namespaces/{config.temporal.namespace}"
        f"/workflows/{handle.id}"
    )
    print("")

    return handle


async def start_workflow(
    project_path: str, features: list[str] | None = None
) -> WorkflowHandle:
    """Start the LLM wrapper development workflow."""
    if features is None:
        features = ["openai", "anthropic", "streaming", "error-handling"]

    workflow_id = generate_workflow_id(WORKFLOW_ID_PREFIX_DEVELOP)

    handle = await start_workflow_helper(
        DevelopLLMWrapperWorkflow.run,
        args=[project_path, features],
        workflow_id=workflow_id,
        description="LLM Wrapper development workflow",
    )

    print("Workflow running... Use Temporal UI to monitor progress.")
    print(
        "To approve stages, use: python -m claude_temporal.client approve <workflow_id>"
    )

    return handle


async def start_iterative_workflow(
    project_path: str, issue: str, max_iterations: int = 5
) -> WorkflowHandle:
    """Start the iterative refinement workflow."""
    workflow_id = generate_workflow_id(WORKFLOW_ID_PREFIX_ITERATIVE)

    handle = await start_workflow_helper(
        IterativeRefinementWorkflow.run,
        args=[project_path, issue, max_iterations],
        workflow_id=workflow_id,
        description="iterative refinement workflow",
    )

    print(f"Issue: {issue}")
    print(f"Max iterations: {max_iterations}")

    return handle


async def start_parallel_workflow(
    project_path: str, features: list[str]
) -> WorkflowHandle:
    """Start the parallel feature development workflow."""
    workflow_id = generate_workflow_id(WORKFLOW_ID_PREFIX_PARALLEL)

    handle = await start_workflow_helper(
        ParallelFeatureDevelopmentWorkflow.run,
        args=[project_path, features],
        workflow_id=workflow_id,
        description="parallel feature development workflow",
    )

    print(f"Features: {', '.join(features)}")

    return handle


async def send_approval(workflow_id: str, approved: bool) -> None:
    """Send approval or rejection signal to a workflow."""
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    if approved:
        await handle.signal("approve")
        print(f"Sent approval signal to workflow {workflow_id}")
    else:
        await handle.signal("reject")
        print(f"Sent rejection signal to workflow {workflow_id}")


async def query_status(workflow_id: str) -> Any:
    """Query the current state of a workflow."""
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    # Get workflow description
    desc = await handle.describe()

    print("")
    print("Workflow State:")
    print(f"  ID: {workflow_id}")
    print(f"  Status: {desc.status.name}")
    print(f"  Started: {desc.start_time}")
    print(f"  Task Queue: {desc.task_queue}")

    # Try to query workflow state
    try:
        state = await handle.query("get_state")
        print("")
        print("Workflow Progress:")
        print(f"  Current Stage: {state.get('current_stage', 'unknown')}")
        print(f"  Total Tokens: {state.get('total_tokens_used', 0)}")
        print(f"  Total Cost: ${state.get('total_cost', 0):.4f}")
        print(f"  Tests Passed: {state.get('tests_passed_count', 0)}")
        print(f"  Snapshots: {len(state.get('snapshots', []))}")
    except Exception as e:
        # Query not supported or workflow completed
        logger.debug(f"Could not query workflow state: {e}")

    return desc


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="Claude Temporal - Manage Claude Code workflows with Temporal"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start development workflow")
    start_parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Path to the project directory (default: current directory)",
    )
    start_parser.add_argument(
        "--features",
        nargs="+",
        help="Features to implement (default: openai anthropic streaming error-handling)",
    )

    # Iterative command
    iter_parser = subparsers.add_parser("iterative", help="Start iterative fix workflow")
    iter_parser.add_argument("project_path", help="Path to the project directory")
    iter_parser.add_argument("issue", help="Description of the issue to fix")
    iter_parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum retry attempts (default: 5)",
    )

    # Parallel command
    parallel_parser = subparsers.add_parser(
        "parallel", help="Start parallel feature development"
    )
    parallel_parser.add_argument("project_path", help="Path to the project directory")
    parallel_parser.add_argument(
        "features", nargs="+", help="Features to develop in parallel"
    )

    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve workflow stage")
    approve_parser.add_argument("workflow_id", help="Workflow ID to approve")

    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject workflow stage")
    reject_parser.add_argument("workflow_id", help="Workflow ID to reject")

    # Status command
    status_parser = subparsers.add_parser("status", help="Query workflow status")
    status_parser.add_argument("workflow_id", help="Workflow ID to query")

    return parser


def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "start":
            asyncio.run(start_workflow(args.project_path, args.features))

        elif args.command == "iterative":
            asyncio.run(
                start_iterative_workflow(
                    args.project_path,
                    args.issue,
                    args.max_iterations,
                )
            )

        elif args.command == "parallel":
            asyncio.run(start_parallel_workflow(args.project_path, args.features))

        elif args.command == "approve":
            asyncio.run(send_approval(args.workflow_id, approved=True))

        elif args.command == "reject":
            asyncio.run(send_approval(args.workflow_id, approved=False))

        elif args.command == "status":
            asyncio.run(query_status(args.workflow_id))

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
