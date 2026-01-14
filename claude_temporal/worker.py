"""
Temporal Worker for Claude Code monitoring.

Run this in a separate terminal to process workflows and activities.

Usage:
    python -m claude_temporal.worker
"""

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from .config import get_config
from .activities import (
    execute_claude_code,
    run_tests,
    estimate_cost,
    create_snapshot,
    notify_developer,
    capture_metrics,
    restore_snapshot,
)
from .workflows import (
    DevelopLLMWrapperWorkflow,
    IterativeRefinementWorkflow,
    ParallelFeatureDevelopmentWorkflow,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_worker():
    """Start the Temporal worker."""
    config = get_config()

    logger.info("Starting Temporal Worker for Claude Code monitoring...")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Connecting to: {config.temporal.address}")

    try:
        # Connect to Temporal server
        client = await Client.connect(
            config.temporal.address,
            namespace=config.temporal.namespace,
        )

        logger.info(f"Connected to Temporal at {config.temporal.address}")

        # Create worker with activities and workflows
        worker = Worker(
            client,
            task_queue=config.temporal.task_queue,
            workflows=[
                DevelopLLMWrapperWorkflow,
                IterativeRefinementWorkflow,
                ParallelFeatureDevelopmentWorkflow,
            ],
            activities=[
                execute_claude_code,
                run_tests,
                estimate_cost,
                create_snapshot,
                notify_developer,
                capture_metrics,
                restore_snapshot,
            ],
        )

        logger.info(f"Worker created, listening on task queue: {config.temporal.task_queue}")
        logger.info("Worker ready to process workflows...")
        logger.info("")

        # Run the worker (blocks until shutdown)
        await worker.run()

    except Exception as e:
        logger.error(f"Worker failed: {e}")
        raise


def main():
    """Entry point for the worker."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")


if __name__ == "__main__":
    main()
