"""
Constants for Claude Temporal integration.

Centralizes magic numbers and configuration values for maintainability.
"""

# Token estimation
CHARS_PER_TOKEN = 4  # Approximate characters per token for Claude models

# Rate limiting
MAX_TOKENS_BEFORE_COOLDOWN = 50000  # Token threshold before triggering cooldown
COOLDOWN_SECONDS = 30  # Cooldown duration after high token usage

# Cost estimation complexity multipliers
COMPLEXITY_MULTIPLIERS = {
    "low": 2,
    "medium": 4,
    "high": 8,
}

# Model pricing (per 1K tokens) as of 2025
MODEL_PRICING = {
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
}

# Default model for cost calculations
DEFAULT_MODEL = "claude-sonnet-4-5"

# Temporal UI base URL
TEMPORAL_UI_BASE_URL = "http://localhost:8233"

# Timeouts (in seconds)
DEFAULT_ACTIVITY_TIMEOUT_SECONDS = 600  # 10 minutes
SNAPSHOT_TIMEOUT_SECONDS = 120  # 2 minutes
NOTIFICATION_TIMEOUT_SECONDS = 60  # 1 minute
APPROVAL_TIMEOUT_HOURS = 1

# Retry policy defaults
RETRY_INITIAL_INTERVAL_SECONDS = 2
RETRY_BACKOFF_COEFFICIENT = 2.0
RETRY_MAX_ATTEMPTS = 3
RETRY_MAX_INTERVAL_SECONDS = 60

# Iterative workflow defaults
DEFAULT_MAX_ITERATIONS = 5
ITERATION_BACKOFF_BASE_SECONDS = 5
ITERATION_BACKOFF_MAX_SECONDS = 30

# Workflow ID prefixes
WORKFLOW_ID_PREFIX_DEVELOP = "llm-wrapper-dev"
WORKFLOW_ID_PREFIX_ITERATIVE = "iterative-fix"
WORKFLOW_ID_PREFIX_PARALLEL = "parallel-dev"
