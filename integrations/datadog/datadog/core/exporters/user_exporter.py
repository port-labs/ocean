from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from datadog.webhook.consts import (
    ROLES_API_PATH_PREFIX,
    AuditTrailAction,
    AuditTrailAssetType,
    AuditTrailEventName,
)

if TYPE_CHECKING:
    from datadog.overrides import UserResourceConfig

# Deletes are excluded on purpose: the full resync reconciles removed users.
# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
CHANGED_USERS_AUDIT_QUERY = (
    f'@evt.name:"{AuditTrailEventName.ACCESS_MANAGEMENT}" '
    f"@asset.type:{AuditTrailAssetType.USER} "
    f"@action:({AuditTrailAction.CREATED} OR {AuditTrailAction.MODIFIED})"
)


class GetUserOptions(GetOptions["UserResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "UserResourceConfig", *, resource_id: str
    ) -> "GetUserOptions":
        return cls(resource_id=resource_id)


class UserExporter(PaginatedExporter[None], SingleResourceExporter[GetUserOptions]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/users/#list-all-users
        """
        url = f"{self.client.api_url}/api/v2/users"
        async for batch in self._paginate_by_page_param(url):
            yield batch

    async def get_changed_users(self, since: datetime) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users created or modified since ``since``, found through audit events.
        Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
        """
        url = f"{self.client.api_url}/api/v2/audit/events/search"
        extra_body = {
            "filter": {
                "query": CHANGED_USERS_AUDIT_QUERY,
                "from": since.astimezone(timezone.utc).isoformat(),
                "to": "now",
            },
            "sort": "-timestamp",
        }

        seen: set[str] = set()
        async for events in self._paginate_by_search_cursor(url, extra_body=extra_body):
            users: list[dict[str, Any]] = []
            for event in events:
                user_id = self._changed_user_id(event)
                if not user_id or user_id in seen:
                    continue
                seen.add(user_id)
                try:
                    user = await self.get_resource(GetUserOptions(resource_id=user_id))
                except HTTPStatusError:
                    logger.warning(
                        f"Skipping user '{user_id}' from audit events; Datadog user fetch failed"
                    )
                    continue
                if user:
                    users.append(user)

            if users:
                yield users

    @staticmethod
    def _changed_user_id(event: dict[str, Any]) -> str | None:
        attributes = event.get("attributes", {}).get("attributes", {})
        path = attributes.get("http", {}).get("url_details", {}).get("path", "")
        if path.startswith(ROLES_API_PATH_PREFIX):
            return None
        return attributes.get("asset", {}).get("id")

    async def get_resource(self, options: GetUserOptions) -> dict[str, Any] | None:
        """Get a single user by ID.
        Docs: https://docs.datadoghq.com/api/latest/users/#get-user-details
        """
        url = f"{self.client.api_url}/api/v2/users/{options.resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("data")

    async def get_resource_by_email(self, email: str) -> dict[str, Any] | None:
        """Get a single user by email.
        Docs: https://docs.datadoghq.com/api/latest/users/#list-all-users
        """
        url = f"{self.client.api_url}/api/v2/users"
        result = await self.client.send_api_request(url, params={"filter": email})
        users = result.get("data") or []
        return users[0] if users else None
