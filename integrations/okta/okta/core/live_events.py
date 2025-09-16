"""Live events processing for Okta integration."""

import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


class OktaLiveEventProcessor:
    """Processor for Okta live events."""

    # Event types that we care about for our resources
    USER_EVENTS: List[str] = [
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

    GROUP_EVENTS: List[str] = [
        "group.lifecycle.create",
        "group.lifecycle.update",
        "group.lifecycle.delete",
        "group.user_membership.add",
        "group.user_membership.remove",
        "group.user_membership.add.end",
        "group.user_membership.remove.end",
    ]

    APPLICATION_EVENTS: List[str] = [
        "app.lifecycle.create",
        "app.lifecycle.update",
        "app.lifecycle.delete",
        "app.user_membership.add",
        "app.user_membership.remove",
        "app.user_membership.add.end",
        "app.user_membership.remove.end",
    ]

    def __init__(self) -> None:
        """Initialize the live event processor."""
        self.all_events = self.USER_EVENTS + self.GROUP_EVENTS + self.APPLICATION_EVENTS

    def process_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a live event and extract relevant data.

        Args:
            event_data: The raw event data from Okta

        Returns:
            Processed event data or None if not relevant
        """
        event_type = event_data.get("eventType")
        if not event_type or event_type not in self.all_events:
            return None

        logger.debug(f"Processing event: {event_type}")

        # Extract common event information
        processed_event = {
            "eventType": event_type,
            "published": event_data.get("published"),
            "eventId": event_data.get("eventId"),
            "actor": event_data.get("actor", {}),
            "target": event_data.get("target", []),
            "debugContext": event_data.get("debugContext", {}),
        }

        # Extract resource-specific data
        if event_type.startswith("user."):
            processed_event["resource_type"] = "user"
            processed_event["resource_data"] = self._extract_user_data(event_data)
        elif event_type.startswith("group."):
            processed_event["resource_type"] = "group"
            processed_event["resource_data"] = self._extract_group_data(event_data)
        elif event_type.startswith("app."):
            processed_event["resource_type"] = "application"
            processed_event["resource_data"] = self._extract_application_data(
                event_data
            )

        return processed_event

    def _extract_target_data(
        self, event_data: Dict[str, Any], target_type: str
    ) -> Dict[str, Any]:
        """Extract data from target array for a specific type.

        Args:
            event_data: The raw event data
            target_type: The target type to look for

        Returns:
            Target data
        """
        targets = event_data.get("target", [])
        target = next((t for t in targets if t.get("type") == target_type), None)
        if target:
            return {
                "id": target.get("id"),
                "displayName": target.get("displayName"),
                "login": target.get("login"),
                "email": target.get("email"),
            }
        return {}

    def _extract_resource_data(
        self, event_data: Dict[str, Any], target_type: str, context_key: str
    ) -> Dict[str, Any]:
        """Extract resource-specific data from event.

        Args:
            event_data: The raw event data
            target_type: The target type to look for
            context_key: The debug context key

        Returns:
            Resource data
        """
        resource_data = self._extract_target_data(event_data, target_type)

        # Extract from debug context
        debug_context = event_data.get("debugContext", {})
        if context_key in debug_context:
            resource_data.update(debug_context[context_key])

        return resource_data

    def _extract_user_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user-specific data from event.

        Args:
            event_data: The raw event data

        Returns:
            User data
        """
        return self._extract_resource_data(event_data, "User", "user")

    def _extract_group_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract group-specific data from event.

        Args:
            event_data: The raw event data

        Returns:
            Group data
        """
        return self._extract_resource_data(event_data, "UserGroup", "group")

    def _extract_application_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract application-specific data from event.

        Args:
            event_data: The raw event data

        Returns:
            Application data
        """
        return self._extract_resource_data(event_data, "AppInstance", "app")

    def get_event_hook_config(
        self,
        webhook_url: str,
        auth_token: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Get configuration for creating an event hook.

        Args:
            webhook_url: The URL to receive events
            auth_token: Optional authentication token
            custom_headers: Optional custom headers

        Returns:
            Event hook configuration
        """
        config: Dict[str, Any] = {
            "name": "Port Ocean Okta Integration",
            "events": {
                "type": "EVENT_TYPE",
                "items": self.all_events,
            },
            "channel": {
                "type": "HTTP",
                "version": "1.0.0",
                "config": {
                    "uri": webhook_url,
                },
            },
            "description": "Event hook for Port Ocean Okta integration live events",
        }

        # Add authentication if provided
        if auth_token:
            config["channel"]["config"]["authScheme"] = {
                "type": "HEADER",
                "key": "Authorization",
                "value": f"Bearer {auth_token}",
            }

        # Add custom headers if provided
        if custom_headers:
            headers: List[Dict[str, str]] = [
                {"key": key, "value": value} for key, value in custom_headers.items()
            ]
            config["channel"]["config"]["headers"] = headers

        return config
