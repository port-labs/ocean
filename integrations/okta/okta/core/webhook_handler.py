"""Webhook handler for Okta live events."""

import logging
from typing import Any, Dict, List, Optional


from okta.core.live_events import OktaLiveEventProcessor

logger = logging.getLogger(__name__)


class OktaWebhookHandler:
    """Handler for processing Okta webhook events."""

    def __init__(self) -> None:
        """Initialize the webhook handler."""
        self.processor = OktaLiveEventProcessor()

    async def handle_webhook(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Handle incoming webhook payload.

        Args:
            payload: The webhook payload
            headers: Optional headers from the request

        Returns:
            List of processed events
        """
        logger.info("Received Okta webhook")

        processed_events = []

        # Okta can send multiple events in a single webhook
        events = payload.get("data", {}).get("events") or [payload]

        for event_data in events:
            try:
                if processed_event := self.processor.process_event(event_data):
                    processed_events.append(processed_event)
                    logger.debug(f"Processed event: {processed_event['eventType']}")
                else:
                    logger.debug(
                        f"Ignored event: {event_data.get('eventType', 'unknown')}"
                    )
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                continue

        logger.info(f"Processed {len(processed_events)} events from webhook")
        return processed_events

    def extract_resource_updates(
        self,
        processed_events: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract resource updates from processed events.

        Args:
            processed_events: List of processed events

        Returns:
            Dictionary mapping resource types to lists of updates
        """
        updates: Dict[str, List[Dict[str, Any]]] = {
            "users": [],
            "groups": [],
            "applications": [],
        }

        for event in processed_events:
            if not (resource_type := event.get("resource_type")) or not (
                resource_data := event.get("resource_data", {})
            ):
                continue

            event_type = event.get("eventType", "")

            # Determine the action based on event type
            action = self._determine_action(event_type)

            update = {
                "action": action,
                "resource_id": resource_data.get("id"),
                "resource_data": resource_data,
                "event_type": event_type,
                "timestamp": event.get("published"),
            }

            if resource_type == "user":
                updates["users"].append(update)
            elif resource_type == "group":
                updates["groups"].append(update)
            elif resource_type == "application":
                updates["applications"].append(update)

        return updates

    def _determine_action(self, event_type: str) -> str:
        """Determine the action from event type.

        Args:
            event_type: The event type

        Returns:
            Action (create, update, delete)
        """
        if any(keyword in event_type for keyword in ["create", "activate", "add"]):
            return "create"
        elif any(keyword in event_type for keyword in ["update", "change"]):
            return "update"
        elif any(
            keyword in event_type for keyword in ["delete", "deactivate", "remove"]
        ):
            return "delete"
        else:
            return "update"  # Default to update for unknown events
