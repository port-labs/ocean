"""Event Hooks client for Okta live events."""

import logging
from typing import Any, Dict, List, Optional

from okta.clients.http.client import OktaClient

logger = logging.getLogger(__name__)


class OktaEventHooksClient(OktaClient):
    """Client for managing Okta event hooks."""

    async def list_event_hooks(self) -> List[Dict[str, Any]]:
        """List all event hooks.

        Returns:
            List of event hooks
        """
        endpoint = "eventHooks"
        response = await self.make_request(endpoint)
        return response.json() if response else []

    async def create_event_hook(
        self,
        name: str,
        events: List[str],
        uri: str,
        auth_scheme: Optional[Dict[str, Any]] = None,
        headers: Optional[List[Dict[str, str]]] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new event hook.

        Args:
            name: Display name for the event hook
            events: List of event types to subscribe to
            uri: The external service endpoint
            auth_scheme: Authentication scheme configuration
            headers: Optional headers to send with requests
            description: Description of the event hook

        Returns:
            Created event hook data
        """
        endpoint = "eventHooks"

        payload: Dict[str, Any] = {
            "name": name,
            "events": {
                "type": "EVENT_TYPE",
                "items": events,
            },
            "channel": {
                "type": "HTTP",
                "version": "1.0.0",
                "config": {
                    "uri": uri,
                },
            },
        }

        if auth_scheme:
            payload["channel"]["config"]["authScheme"] = auth_scheme

        if headers:
            payload["channel"]["config"]["headers"] = headers

        if description:
            payload["description"] = description

        response = await self.make_request(endpoint, method="POST", json_data=payload)
        return response.json()

    async def get_event_hook(self, hook_id: str) -> Dict[str, Any]:
        """Get a specific event hook by ID.

        Args:
            hook_id: The event hook ID

        Returns:
            Event hook data
        """
        endpoint = f"eventHooks/{hook_id}"
        response = await self.make_request(endpoint)
        return response.json()

    async def update_event_hook(
        self,
        hook_id: str,
        name: Optional[str] = None,
        events: Optional[List[str]] = None,
        uri: Optional[str] = None,
        auth_scheme: Optional[Dict[str, Any]] = None,
        headers: Optional[List[Dict[str, str]]] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing event hook.

        Args:
            hook_id: The event hook ID
            name: Display name for the event hook
            events: List of event types to subscribe to
            uri: The external service endpoint
            auth_scheme: Authentication scheme configuration
            headers: Optional headers to send with requests
            description: Description of the event hook
            status: Status of the event hook (ACTIVE/INACTIVE)

        Returns:
            Updated event hook data
        """
        endpoint = f"eventHooks/{hook_id}"

        payload: Dict[str, Any] = {}

        if name is not None:
            payload["name"] = name

        if events is not None:
            payload["events"] = {
                "type": "EVENT_TYPE",
                "items": events,
            }

        if any([uri is not None, auth_scheme is not None, headers is not None]):
            payload["channel"] = {
                "type": "HTTP",
                "version": "1.0.0",
                "config": {},
            }

            if uri is not None:
                payload["channel"]["config"]["uri"] = uri

            if auth_scheme is not None:
                payload["channel"]["config"]["authScheme"] = auth_scheme

            if headers is not None:
                payload["channel"]["config"]["headers"] = headers

        if description is not None:
            payload["description"] = description

        if status is not None:
            payload["status"] = status

        response = await self.make_request(endpoint, method="PUT", json_data=payload)
        return response.json()

    async def delete_event_hook(self, hook_id: str) -> None:
        """Delete an event hook.

        Args:
            hook_id: The event hook ID
        """
        endpoint = f"eventHooks/{hook_id}"
        await self.make_request(endpoint, method="DELETE")

    async def verify_event_hook(self, hook_id: str) -> Dict[str, Any]:
        """Verify an event hook.

        Args:
            hook_id: The event hook ID

        Returns:
            Verification result
        """
        endpoint = f"eventHooks/{hook_id}/verify"
        response = await self.make_request(endpoint, method="POST")
        return response.json()

    async def deactivate_event_hook(self, hook_id: str) -> Dict[str, Any]:
        """Deactivate an event hook.

        Args:
            hook_id: The event hook ID

        Returns:
            Deactivated event hook data
        """
        endpoint = f"eventHooks/{hook_id}/lifecycle/deactivate"
        response = await self.make_request(endpoint, method="POST")
        return response.json()

    async def activate_event_hook(self, hook_id: str) -> Dict[str, Any]:
        """Activate an event hook.

        Args:
            hook_id: The event hook ID

        Returns:
            Activated event hook data
        """
        endpoint = f"eventHooks/{hook_id}/lifecycle/activate"
        response = await self.make_request(endpoint, method="POST")
        return response.json()
