"""
Notification services for Claude Temporal integration.

Provides pluggable notification backends for human-in-the-loop approvals.
Supports console, Slack, email, and webhook notifications.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .models import NotificationParams


logger = logging.getLogger(__name__)


class NotificationService(ABC):
    """
    Abstract base class for notification services.

    Implement this interface to add new notification backends
    (e.g., Slack, email, PagerDuty, etc.)
    """

    @abstractmethod
    async def send(self, params: NotificationParams) -> bool:
        """
        Send a notification.

        Args:
            params: Notification parameters including stage, message, and files

        Returns:
            True if notification was sent successfully
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the service name for logging."""
        pass


class ConsoleNotificationService(NotificationService):
    """
    Console-based notification service.

    Prints notifications to stdout for local development.
    """

    async def send(self, params: NotificationParams) -> bool:
        """Print notification to console."""
        separator = "=" * 50

        print(f"\n{separator}")
        print(f"NOTIFICATION: Stage '{params.stage}' requires attention")
        print(f"Message: {params.message}")
        print(f"Files changed: {len(params.files_changed)}")

        if params.files_changed:
            for file in params.files_changed[:10]:  # Show first 10 files
                print(f"  - {file}")
            if len(params.files_changed) > 10:
                print(f"  ... and {len(params.files_changed) - 10} more")

        if params.diff_url:
            print(f"View diff: {params.diff_url}")

        print(f"{separator}\n")

        logger.info(f"Console notification sent for stage: {params.stage}")
        return True

    def get_name(self) -> str:
        return "console"


class LoggingNotificationService(NotificationService):
    """
    Logging-based notification service.

    Logs notifications for production environments where
    console output may not be visible.
    """

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level

    async def send(self, params: NotificationParams) -> bool:
        """Log notification."""
        logger.log(
            self.log_level,
            f"Notification: stage={params.stage}, "
            f"message={params.message}, "
            f"files_changed={len(params.files_changed)}",
        )
        return True

    def get_name(self) -> str:
        return "logging"


@dataclass
class SlackConfig:
    """Configuration for Slack notifications."""
    webhook_url: str
    channel: Optional[str] = None
    username: str = "Claude Temporal"


class SlackNotificationService(NotificationService):
    """
    Slack notification service.

    Sends notifications to a Slack channel via webhook.
    Requires the `httpx` package for HTTP requests.
    """

    def __init__(self, config: SlackConfig):
        self.config = config

    async def send(self, params: NotificationParams) -> bool:
        """Send notification to Slack."""
        try:
            import httpx

            files_list = "\n".join(f"- {f}" for f in params.files_changed[:10])
            if len(params.files_changed) > 10:
                files_list += f"\n... and {len(params.files_changed) - 10} more"

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Stage '{params.stage}' requires attention",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": params.message,
                    },
                },
            ]

            if params.files_changed:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Files changed:*\n```{files_list}```",
                    },
                })

            if params.diff_url:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{params.diff_url}|View Diff>",
                    },
                })

            payload = {
                "username": self.config.username,
                "blocks": blocks,
            }
            if self.config.channel:
                payload["channel"] = self.config.channel

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info(f"Slack notification sent for stage: {params.stage}")
            return True

        except ImportError:
            logger.error("httpx package not installed. Run: pip install httpx")
            return False
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def get_name(self) -> str:
        return "slack"


@dataclass
class WebhookConfig:
    """Configuration for generic webhook notifications."""
    url: str
    headers: Optional[dict[str, str]] = None


class WebhookNotificationService(NotificationService):
    """
    Generic webhook notification service.

    Sends notifications to any HTTP endpoint.
    """

    def __init__(self, config: WebhookConfig):
        self.config = config

    async def send(self, params: NotificationParams) -> bool:
        """Send notification to webhook."""
        try:
            import httpx

            payload = {
                "stage": params.stage,
                "message": params.message,
                "files_changed": params.files_changed,
                "diff_url": params.diff_url,
            }

            headers = self.config.headers or {}
            headers.setdefault("Content-Type", "application/json")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.url,
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info(f"Webhook notification sent for stage: {params.stage}")
            return True

        except ImportError:
            logger.error("httpx package not installed. Run: pip install httpx")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def get_name(self) -> str:
        return "webhook"


class CompositeNotificationService(NotificationService):
    """
    Composite notification service that sends to multiple backends.

    Useful for sending notifications to both Slack and console, for example.
    """

    def __init__(self, services: list[NotificationService]):
        self.services = services

    async def send(self, params: NotificationParams) -> bool:
        """Send notification to all configured services."""
        results = []
        for service in self.services:
            try:
                result = await service.send(params)
                results.append(result)
                logger.debug(f"Notification via {service.get_name()}: {result}")
            except Exception as e:
                logger.error(f"Notification via {service.get_name()} failed: {e}")
                results.append(False)

        # Return True if at least one notification succeeded
        return any(results)

    def get_name(self) -> str:
        names = ", ".join(s.get_name() for s in self.services)
        return f"composite({names})"


def get_notification_service(config: Optional[dict] = None) -> NotificationService:
    """
    Factory function to create the appropriate notification service.

    Args:
        config: Optional configuration dict with 'type' and service-specific settings

    Returns:
        Configured NotificationService instance
    """
    if config is None:
        return ConsoleNotificationService()

    service_type = config.get("type", "console")

    if service_type == "console":
        return ConsoleNotificationService()

    elif service_type == "logging":
        return LoggingNotificationService()

    elif service_type == "slack":
        return SlackNotificationService(
            SlackConfig(
                webhook_url=config["webhook_url"],
                channel=config.get("channel"),
                username=config.get("username", "Claude Temporal"),
            )
        )

    elif service_type == "webhook":
        return WebhookNotificationService(
            WebhookConfig(
                url=config["url"],
                headers=config.get("headers"),
            )
        )

    else:
        logger.warning(f"Unknown notification type: {service_type}, using console")
        return ConsoleNotificationService()
