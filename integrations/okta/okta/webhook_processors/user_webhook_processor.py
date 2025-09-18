"""Webhook processor for Okta user events."""

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from okta.webhook_processors.okta_base_webhook_processor import OktaBaseWebhookProcessor
import inspect


class UserWebhookProcessor(OktaBaseWebhookProcessor):
    """Webhook processor for Okta user events."""

    # User-related event types
    USER_EVENTS = [
        "user.lifecycle.create",
        "user.lifecycle.activate",
        "user.lifecycle.deactivate",
        "user.lifecycle.suspend",
        "user.lifecycle.unsuspend",
        "user.lifecycle.delete",
        "user.lifecycle.unlock",
        "user.lifecycle.resetPassword",
        "user.lifecycle.expirePassword",
        "user.lifecycle.forgotPassword",
        "user.lifecycle.changePassword",
        "user.lifecycle.changeRecoveryQuestion",
        "user.lifecycle.activate.end",
        "user.lifecycle.deactivate.end",
        "user.lifecycle.suspend.end",
        "user.lifecycle.unsuspend.end",
        "user.lifecycle.delete.end",
        "user.lifecycle.unlock.end",
        "user.lifecycle.resetPassword.end",
        "user.lifecycle.expirePassword.end",
        "user.lifecycle.forgotPassword.end",
        "user.lifecycle.changePassword.end",
        "user.lifecycle.changeRecoveryQuestion.end",
    ]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is a user-related event.

        Args:
            event: The webhook event

        Returns:
            True if this is a user event, False otherwise
        """
        event_type = event.payload.get("eventType", "")
        return event_type in self.USER_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get the resource kinds that this event affects.

        Args:
            event: The webhook event

        Returns:
            List of resource kinds
        """
        return ["okta-user"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the user webhook event.

        Args:
            payload: The webhook payload
            resource_config: The resource configuration

        Returns:
            Webhook event results
        """

        async def _maybe_await(value):  # type: ignore[no-untyped-def]
            return await value if inspect.isawaitable(value) else value

        # Extract user ID from the event
        user_id = self._extract_user_id(payload)
        if not user_id:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        event_type = payload.get("eventType", "")

        # Handle deletion events
        if "delete" in event_type:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": user_id}],
            )

        # For create/update events, fetch the current user data
        try:
            user_data = await _maybe_await(self.client.get_user(user_id))
            groups = await _maybe_await(self.client.get_user_groups(user_id))
            apps = await _maybe_await(self.client.get_user_apps(user_id))
            if isinstance(user_data, dict):
                user_data["groups"] = groups
                user_data["applications"] = apps

            return WebhookEventRawResults(
                updated_raw_results=[user_data],
                deleted_raw_results=[],
            )
        except Exception:
            # If we can't fetch the user, it might have been deleted
            # Return it as a deletion
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": user_id}],
            )

    def _extract_user_id(self, payload: EventPayload) -> str | None:
        """Extract user ID from the event payload.

        Args:
            payload: The webhook payload

        Returns:
            User ID if found, None otherwise
        """
        # Try to extract from target array
        targets = payload.get("target", [])
        for target in targets:
            if target.get("type") == "User":
                return target.get("id")
        # Fallback: if targets exist, return first id
        if targets and isinstance(targets, list) and isinstance(targets[0], dict):
            if "id" in targets[0]:
                return targets[0]["id"]

        # Try to extract from debug context
        debug_context = payload.get("debugContext", {})
        return (
            debug_context.get("user", {}).get("id") if "user" in debug_context else None
        )
