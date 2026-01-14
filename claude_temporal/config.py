"""
Configuration management for Claude Temporal integration.

Supports environment-based configuration (dev, staging, prod)
using a mapping pattern for cleaner code.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from .constants import TEMPORAL_UI_BASE_URL

# Load .env file if present
load_dotenv()


@dataclass
class TemporalConfig:
    """Temporal server connection settings."""
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "claude-code-llm-wrapper"
    ui_base_url: str = TEMPORAL_UI_BASE_URL


@dataclass
class ClaudeConfig:
    """Claude Code execution settings."""
    max_tokens: int = 8000
    temperature: float = 0.3
    timeout_seconds: int = 600  # 10 minutes


@dataclass
class WorkerConfig:
    """Worker process settings."""
    max_concurrent_activities: int = 5
    max_concurrent_workflows: int = 10


@dataclass
class NotificationConfig:
    """Notification service settings."""
    type: str = "console"  # console, logging, slack, webhook
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_headers: Optional[dict[str, str]] = None


@dataclass
class Config:
    """Main configuration container."""
    temporal: TemporalConfig
    claude: ClaudeConfig
    worker: WorkerConfig
    notification: NotificationConfig
    environment: str
    project_path: Optional[str] = None
    metrics_file: str = "/tmp/claude-code-metrics.jsonl"


# Environment-specific Claude configurations using mapping pattern
CLAUDE_CONFIG_BY_ENV = {
    "production": ClaudeConfig(
        max_tokens=8000,
        temperature=0.2,
        timeout_seconds=600,
    ),
    "staging": ClaudeConfig(
        max_tokens=8000,
        temperature=0.3,
        timeout_seconds=600,
    ),
    "development": ClaudeConfig(
        max_tokens=100000,
        temperature=0.3,
        timeout_seconds=1800,  # 30 min for dev
    ),
}


def _parse_int(value: Optional[str], default: int) -> int:
    """Safely parse an integer from environment variable."""
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: Optional[str], default: float) -> float:
    """Safely parse a float from environment variable."""
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_temporal_config() -> TemporalConfig:
    """Load Temporal configuration from environment."""
    return TemporalConfig(
        address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "claude-code-llm-wrapper"),
        ui_base_url=os.getenv("TEMPORAL_UI_BASE_URL", TEMPORAL_UI_BASE_URL),
    )


def load_claude_config(environment: str) -> ClaudeConfig:
    """
    Load Claude configuration for the given environment.

    Uses environment-specific defaults with env var overrides.
    """
    # Get base config for environment
    base_config = CLAUDE_CONFIG_BY_ENV.get(
        environment,
        CLAUDE_CONFIG_BY_ENV["development"]
    )

    # Allow env vars to override
    return ClaudeConfig(
        max_tokens=_parse_int(
            os.getenv("CLAUDE_MAX_TOKENS"),
            base_config.max_tokens
        ),
        temperature=_parse_float(
            os.getenv("CLAUDE_TEMPERATURE"),
            base_config.temperature
        ),
        timeout_seconds=_parse_int(
            os.getenv("CLAUDE_TIMEOUT"),
            base_config.timeout_seconds
        ),
    )


def load_worker_config() -> WorkerConfig:
    """Load worker configuration from environment."""
    return WorkerConfig(
        max_concurrent_activities=_parse_int(
            os.getenv("WORKER_MAX_ACTIVITIES"),
            5
        ),
        max_concurrent_workflows=_parse_int(
            os.getenv("WORKER_MAX_WORKFLOWS"),
            10
        ),
    )


def load_notification_config() -> NotificationConfig:
    """Load notification configuration from environment."""
    return NotificationConfig(
        type=os.getenv("NOTIFICATION_TYPE", "console"),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        slack_channel=os.getenv("SLACK_CHANNEL"),
        webhook_url=os.getenv("NOTIFICATION_WEBHOOK_URL"),
    )


def load_config(environment: Optional[str] = None) -> Config:
    """
    Load configuration based on environment.

    Args:
        environment: One of 'development', 'staging', 'production'.
                    Defaults to CLAUDE_TEMPORAL_ENV or 'development'.

    Returns:
        Config object with all settings.
    """
    env = environment or os.getenv("CLAUDE_TEMPORAL_ENV", "development")

    return Config(
        temporal=load_temporal_config(),
        claude=load_claude_config(env),
        worker=load_worker_config(),
        notification=load_notification_config(),
        environment=env,
        project_path=os.getenv("PROJECT_PATH"),
        metrics_file=os.getenv("METRICS_FILE", "/tmp/claude-code-metrics.jsonl"),
    )


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
