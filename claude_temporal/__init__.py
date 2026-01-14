"""
Claude Temporal - Temporal.io integration for monitoring Claude Code workflows.

This package provides durable, observable, and recoverable LLM-assisted
development workflows using Temporal.io orchestration.
"""

__version__ = "0.1.0"

# Models
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

# Activities
from .activities import (
    execute_claude_code,
    run_tests,
    estimate_cost,
    create_snapshot,
    notify_developer,
    capture_metrics,
    restore_snapshot,
)

# Workflows
from .workflows import (
    DevelopLLMWrapperWorkflow,
    IterativeRefinementWorkflow,
    ParallelFeatureDevelopmentWorkflow,
)

# Configuration
from .config import (
    Config,
    TemporalConfig,
    ClaudeConfig,
    WorkerConfig,
    NotificationConfig,
    get_config,
    load_config,
    reset_config,
)

# Git utilities
from .git_utils import (
    GitOperations,
    GitStatus,
    GitStats,
    GitOperationResult,
)

# Notification services
from .notification import (
    NotificationService,
    ConsoleNotificationService,
    LoggingNotificationService,
    SlackNotificationService,
    WebhookNotificationService,
    CompositeNotificationService,
    get_notification_service,
)

# Test runners
from .test_runner import (
    TestRunner,
    NpmTestRunner,
    PytestRunner,
    CargoTestRunner,
    GoTestRunner,
    AutoDetectTestRunner,
    get_test_runner,
)

# Stage configuration
from .stages import (
    DevelopmentStage,
    StageTemplate,
    StageConfig,
    LLM_WRAPPER_STAGES,
    API_DEVELOPMENT_STAGES,
    FRONTEND_STAGES,
    get_default_stages,
    create_stage_config,
)

# Constants
from .constants import (
    CHARS_PER_TOKEN,
    MAX_TOKENS_BEFORE_COOLDOWN,
    COOLDOWN_SECONDS,
    MODEL_PRICING,
    DEFAULT_MODEL,
    TEMPORAL_UI_BASE_URL,
)

__all__ = [
    # Version
    "__version__",
    # Models
    "ClaudeCodeInput",
    "ClaudeCodeResult",
    "TestResult",
    "CostEstimate",
    "WorkflowState",
    "NotificationParams",
    "MetricsData",
    "FeatureResult",
    # Activities
    "execute_claude_code",
    "run_tests",
    "estimate_cost",
    "create_snapshot",
    "notify_developer",
    "capture_metrics",
    "restore_snapshot",
    # Workflows
    "DevelopLLMWrapperWorkflow",
    "IterativeRefinementWorkflow",
    "ParallelFeatureDevelopmentWorkflow",
    # Configuration
    "Config",
    "TemporalConfig",
    "ClaudeConfig",
    "WorkerConfig",
    "NotificationConfig",
    "get_config",
    "load_config",
    "reset_config",
    # Git utilities
    "GitOperations",
    "GitStatus",
    "GitStats",
    "GitOperationResult",
    # Notification services
    "NotificationService",
    "ConsoleNotificationService",
    "LoggingNotificationService",
    "SlackNotificationService",
    "WebhookNotificationService",
    "CompositeNotificationService",
    "get_notification_service",
    # Test runners
    "TestRunner",
    "NpmTestRunner",
    "PytestRunner",
    "CargoTestRunner",
    "GoTestRunner",
    "AutoDetectTestRunner",
    "get_test_runner",
    # Stage configuration
    "DevelopmentStage",
    "StageTemplate",
    "StageConfig",
    "LLM_WRAPPER_STAGES",
    "API_DEVELOPMENT_STAGES",
    "FRONTEND_STAGES",
    "get_default_stages",
    "create_stage_config",
    # Constants
    "CHARS_PER_TOKEN",
    "MAX_TOKENS_BEFORE_COOLDOWN",
    "COOLDOWN_SECONDS",
    "MODEL_PRICING",
    "DEFAULT_MODEL",
    "TEMPORAL_UI_BASE_URL",
]
