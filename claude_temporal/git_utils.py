"""
Git utilities for Claude Temporal integration.

Provides a clean abstraction over git subprocess operations
with proper error handling and typed results.
"""

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GitStats:
    """Statistics from git diff output."""
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class GitStatus:
    """Result from git status operation."""
    files_changed: list[str] = field(default_factory=list)
    raw_output: str = ""


@dataclass
class GitOperationResult:
    """Result from a git operation."""
    success: bool
    output: str = ""
    error: str = ""


class GitOperations:
    """
    Encapsulates git operations with async subprocess execution.

    Provides a clean interface for common git operations used
    in the Claude Temporal workflow.
    """

    def __init__(self, working_directory: str):
        """
        Initialize git operations for a directory.

        Args:
            working_directory: Path to the git repository

        Raises:
            ValueError: If the directory doesn't exist
        """
        self.cwd = Path(working_directory)
        if not self.cwd.exists():
            raise ValueError(f"Directory does not exist: {working_directory}")

    async def _run_command(self, *args: str) -> GitOperationResult:
        """
        Run a git command and return the result.

        Args:
            *args: Git command arguments (e.g., "status", "--porcelain")

        Returns:
            GitOperationResult with success status and output
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", *args,
                cwd=str(self.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            return GitOperationResult(
                success=proc.returncode == 0,
                output=stdout.decode().strip() if stdout else "",
                error=stderr.decode().strip() if stderr else "",
            )
        except Exception as e:
            return GitOperationResult(
                success=False,
                error=str(e),
            )

    async def get_status(self) -> GitStatus:
        """
        Get git status with changed files.

        Returns:
            GitStatus with list of changed files
        """
        result = await self._run_command("status", "--porcelain")

        if not result.success or not result.output:
            return GitStatus()

        files = []
        for line in result.output.split("\n"):
            if line.strip():
                # Git status format: XY filename
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1])

        return GitStatus(
            files_changed=files,
            raw_output=result.output,
        )

    async def get_diff_stats(self) -> GitStats:
        """
        Get diff statistics (lines added/removed).

        Returns:
            GitStats with addition and deletion counts
        """
        result = await self._run_command("diff", "--stat")

        if not result.success or not result.output:
            return GitStats()

        return self._parse_diff_stats(result.output)

    @staticmethod
    def _parse_diff_stats(diff_output: str) -> GitStats:
        """
        Parse git diff --stat output for additions/deletions.

        Args:
            diff_output: Raw output from git diff --stat

        Returns:
            GitStats with parsed counts
        """
        match = re.search(r"(\d+) insertions?.*?(\d+) deletions?", diff_output)
        if match:
            return GitStats(
                lines_added=int(match.group(1)),
                lines_removed=int(match.group(2)),
            )
        return GitStats()

    async def create_snapshot(self, snapshot_id: str) -> GitOperationResult:
        """
        Create a snapshot commit for rollback capability.

        Args:
            snapshot_id: Unique identifier for the snapshot

        Returns:
            GitOperationResult indicating success/failure
        """
        # Stage all changes
        stage_result = await self._run_command("add", "-A")
        if not stage_result.success:
            return stage_result

        # Create commit with snapshot message
        return await self._run_command(
            "commit", "-m", f"Snapshot: {snapshot_id}", "--allow-empty"
        )

    async def restore_snapshot(self, snapshot_id: str) -> GitOperationResult:
        """
        Restore to a previous snapshot.

        Args:
            snapshot_id: The snapshot identifier to restore

        Returns:
            GitOperationResult indicating success/failure
        """
        # Find the commit with the snapshot message
        log_result = await self._run_command(
            "log", "--oneline", "--grep", f"Snapshot: {snapshot_id}"
        )

        if not log_result.success or not log_result.output:
            return GitOperationResult(
                success=False,
                error=f"Snapshot not found: {snapshot_id}",
            )

        # Get the commit hash (first word of output)
        commit_hash = log_result.output.split()[0]

        # Reset to that commit
        return await self._run_command("reset", "--hard", commit_hash)

    async def create_branch(self, branch_name: str) -> GitOperationResult:
        """
        Create and switch to a new branch.

        Args:
            branch_name: Name for the new branch

        Returns:
            GitOperationResult indicating success/failure
        """
        return await self._run_command("checkout", "-b", branch_name)

    async def get_current_branch(self) -> Optional[str]:
        """
        Get the current branch name.

        Returns:
            Branch name or None if not in a git repo
        """
        result = await self._run_command("branch", "--show-current")
        return result.output if result.success else None
