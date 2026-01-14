"""
Test runner abstractions for Claude Temporal integration.

Provides a strategy pattern for running tests across different
test frameworks (npm/jest, pytest, cargo, go test, etc.)
"""

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .models import TestResult


logger = logging.getLogger(__name__)


class TestRunner(ABC):
    """
    Abstract base class for test runners.

    Implement this interface to add support for new test frameworks.
    """

    @abstractmethod
    async def run(self, project_path: str) -> TestResult:
        """
        Run tests and return results.

        Args:
            project_path: Path to the project directory

        Returns:
            TestResult with pass/fail status and details
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the test runner name."""
        pass

    @abstractmethod
    def is_available(self, project_path: str) -> bool:
        """
        Check if this test runner is available for the project.

        Args:
            project_path: Path to the project directory

        Returns:
            True if this runner can be used
        """
        pass


class NpmTestRunner(TestRunner):
    """
    Test runner for npm/Node.js projects using Jest or similar.
    """

    async def run(self, project_path: str) -> TestResult:
        """Run npm test with JSON output."""
        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "test", "--", "--json", "--coverage",
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()
            duration_ms = int((time.time() - start_time) * 1000)

            output = stdout.decode() if stdout else stderr.decode()

            return self._parse_result(output, proc.returncode, duration_ms)

        except FileNotFoundError:
            return TestResult(
                success=False,
                total_tests=0,
                passed=0,
                failed=1,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=["npm not found"],
            )

    def _parse_result(
        self, output: str, return_code: int, duration_ms: int
    ) -> TestResult:
        """Parse npm test JSON output."""
        try:
            data = json.loads(output)
            return TestResult(
                success=data.get("success", return_code == 0),
                total_tests=data.get("numTotalTests", 0),
                passed=data.get("numPassedTests", 0),
                failed=data.get("numFailedTests", 0),
                duration_ms=duration_ms,
                errors=[],
                coverage=data.get("coverageMap", {})
                .get("total", {})
                .get("lines", {})
                .get("pct"),
            )
        except json.JSONDecodeError:
            # Fallback for non-JSON output
            success = return_code == 0
            return TestResult(
                success=success,
                total_tests=0,
                passed=0 if not success else 1,
                failed=1 if not success else 0,
                duration_ms=duration_ms,
                errors=[output] if not success else [],
            )

    def get_name(self) -> str:
        return "npm"

    def is_available(self, project_path: str) -> bool:
        """Check if package.json exists."""
        return (Path(project_path) / "package.json").exists()


class PytestRunner(TestRunner):
    """
    Test runner for Python projects using pytest.
    """

    async def run(self, project_path: str) -> TestResult:
        """Run pytest with short traceback."""
        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                "pytest", "--tb=short", "-q",
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()
            duration_ms = int((time.time() - start_time) * 1000)

            output = stdout.decode() if stdout else stderr.decode()

            return self._parse_result(output, proc.returncode, duration_ms)

        except FileNotFoundError:
            return TestResult(
                success=False,
                total_tests=0,
                passed=0,
                failed=1,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=["pytest not found"],
            )

    def _parse_result(
        self, output: str, return_code: int, duration_ms: int
    ) -> TestResult:
        """Parse pytest output for test counts."""
        success = return_code == 0

        # Parse passed count
        passed_match = re.search(r"(\d+) passed", output)
        passed = int(passed_match.group(1)) if passed_match else 0

        # Parse failed count
        failed_match = re.search(r"(\d+) failed", output)
        failed = int(failed_match.group(1)) if failed_match else 0

        # Parse error count
        error_match = re.search(r"(\d+) error", output)
        errors_count = int(error_match.group(1)) if error_match else 0

        return TestResult(
            success=success,
            total_tests=passed + failed + errors_count,
            passed=passed,
            failed=failed + errors_count,
            duration_ms=duration_ms,
            errors=[output] if not success else [],
        )

    def get_name(self) -> str:
        return "pytest"

    def is_available(self, project_path: str) -> bool:
        """Check if pytest.ini, pyproject.toml, or setup.py exists."""
        path = Path(project_path)
        return (
            (path / "pytest.ini").exists()
            or (path / "pyproject.toml").exists()
            or (path / "setup.py").exists()
            or (path / "tests").is_dir()
        )


class CargoTestRunner(TestRunner):
    """
    Test runner for Rust projects using cargo test.
    """

    async def run(self, project_path: str) -> TestResult:
        """Run cargo test."""
        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                "cargo", "test", "--", "--format=json", "-Z", "unstable-options",
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()
            duration_ms = int((time.time() - start_time) * 1000)

            output = stdout.decode() if stdout else stderr.decode()
            success = proc.returncode == 0

            # Parse cargo test output
            passed = len(re.findall(r"test .+ \.\.\. ok", output))
            failed = len(re.findall(r"test .+ \.\.\. FAILED", output))

            return TestResult(
                success=success,
                total_tests=passed + failed,
                passed=passed,
                failed=failed,
                duration_ms=duration_ms,
                errors=[output] if not success else [],
            )

        except FileNotFoundError:
            return TestResult(
                success=False,
                total_tests=0,
                passed=0,
                failed=1,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=["cargo not found"],
            )

    def get_name(self) -> str:
        return "cargo"

    def is_available(self, project_path: str) -> bool:
        """Check if Cargo.toml exists."""
        return (Path(project_path) / "Cargo.toml").exists()


class GoTestRunner(TestRunner):
    """
    Test runner for Go projects.
    """

    async def run(self, project_path: str) -> TestResult:
        """Run go test."""
        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                "go", "test", "-v", "./...",
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()
            duration_ms = int((time.time() - start_time) * 1000)

            output = stdout.decode() if stdout else stderr.decode()
            success = proc.returncode == 0

            # Parse go test output
            passed = len(re.findall(r"--- PASS:", output))
            failed = len(re.findall(r"--- FAIL:", output))

            return TestResult(
                success=success,
                total_tests=passed + failed,
                passed=passed,
                failed=failed,
                duration_ms=duration_ms,
                errors=[output] if not success else [],
            )

        except FileNotFoundError:
            return TestResult(
                success=False,
                total_tests=0,
                passed=0,
                failed=1,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=["go not found"],
            )

    def get_name(self) -> str:
        return "go"

    def is_available(self, project_path: str) -> bool:
        """Check if go.mod exists."""
        return (Path(project_path) / "go.mod").exists()


class AutoDetectTestRunner(TestRunner):
    """
    Automatically detects and uses the appropriate test runner.

    Checks for project files in order of priority and uses
    the first matching test framework.
    """

    def __init__(self):
        self.runners: list[TestRunner] = [
            NpmTestRunner(),
            PytestRunner(),
            CargoTestRunner(),
            GoTestRunner(),
        ]
        self._detected_runner: Optional[TestRunner] = None

    async def run(self, project_path: str) -> TestResult:
        """Detect and run appropriate test framework."""
        runner = self._detect_runner(project_path)

        if runner is None:
            return TestResult(
                success=False,
                total_tests=0,
                passed=0,
                failed=1,
                duration_ms=0,
                errors=["No supported test framework detected"],
            )

        logger.info(f"Using {runner.get_name()} test runner")
        return await runner.run(project_path)

    def _detect_runner(self, project_path: str) -> Optional[TestRunner]:
        """Detect which test runner to use."""
        for runner in self.runners:
            if runner.is_available(project_path):
                self._detected_runner = runner
                return runner
        return None

    def get_name(self) -> str:
        if self._detected_runner:
            return f"auto({self._detected_runner.get_name()})"
        return "auto"

    def is_available(self, project_path: str) -> bool:
        """Check if any test runner is available."""
        return any(r.is_available(project_path) for r in self.runners)


def get_test_runner(framework: Optional[str] = None) -> TestRunner:
    """
    Factory function to get the appropriate test runner.

    Args:
        framework: Optional framework name (npm, pytest, cargo, go).
                  If None, auto-detection is used.

    Returns:
        Configured TestRunner instance
    """
    runners = {
        "npm": NpmTestRunner,
        "pytest": PytestRunner,
        "cargo": CargoTestRunner,
        "go": GoTestRunner,
    }

    if framework is None:
        return AutoDetectTestRunner()

    runner_class = runners.get(framework.lower())
    if runner_class:
        return runner_class()

    logger.warning(f"Unknown framework: {framework}, using auto-detection")
    return AutoDetectTestRunner()
