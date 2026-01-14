"""
Data models for Claude Temporal integration.

Type-safe dataclasses for all workflow and activity inputs/outputs.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ClaudeCodeInput:
    """Input parameters for Claude Code execution."""
    prompt: str
    working_directory: str
    max_tokens: int = 8000
    temperature: float = 0.3


@dataclass
class ClaudeCodeResult:
    """Result from Claude Code execution with telemetry."""
    output: str
    tokens_used: int
    cost: float
    duration_ms: int
    files_modified: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    diff_url: Optional[str] = None


@dataclass
class TestResult:
    """Result from test suite execution."""
    success: bool
    total_tests: int
    passed: int
    failed: int
    duration_ms: int
    errors: list[str] = field(default_factory=list)
    coverage: Optional[float] = None


@dataclass
class CostEstimate:
    """Pre-execution cost estimate."""
    estimated: float
    model: str
    tokens_estimate: int


@dataclass
class WorkflowState:
    """Current state of a development workflow."""
    current_stage: str = "initializing"
    total_tokens_used: int = 0
    total_cost: float = 0.0
    tests_passed_count: int = 0
    snapshots: list[str] = field(default_factory=list)
    approved: Optional[bool] = None


@dataclass
class NotificationParams:
    """Parameters for developer notification."""
    stage: str
    message: str
    files_changed: list[str] = field(default_factory=list)
    diff_url: Optional[str] = None


@dataclass
class MetricsData:
    """Metrics data for observability."""
    stage: str
    tokens_used: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    files_modified: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    tests_pass: bool = True
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FeatureResult:
    """Result from parallel feature development."""
    feature: str
    branch: str
    success: bool
    tokens_used: int = 0
    test_results: Optional[TestResult] = None
