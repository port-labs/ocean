from enum import StrEnum
from typing import Any, AsyncGenerator, Optional
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 50


class ResourceKey(StrEnum):
    COMPONENT_GROUPS = "component-groups"
    COMPONENTS = "components"
    INCIDENTS = "incidents"


class PerPageParam(StrEnum):
    PER_PAGE = "per_page"
    LIMIT = "limit"


class StatusPageClient:
    BASE_ENDPOINT = "v1/pages"

    def __init__(
        self,
        statuspage_host: str,
        statuspage_api_key: str,
        statuspage_ids: Optional[list[str]] = None,
    ) -> None:
        logger.info(f"Initializing StatusPageClient with host: {statuspage_host}")
        self.statuspage_host = statuspage_host
        self.statuspage_api_key = statuspage_api_key
        self.statuspage_ids = statuspage_ids or []
        self.client = http_async_client
        self.api_auth_header = {"Authorization": self.statuspage_api_key}
        self.client.headers.update(self.api_auth_header)

    @property
    def pages_base_endpoint(self) -> str:
        return f"{self.statuspage_host}/{self.BASE_ENDPOINT}"

    async def _get_paginated_resources(
        self, url: str, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = 1
        while True:
            params["page"] = page
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            yield data
            page += 1

    async def get_pages(self) -> list[dict[str, Any]]:
        async for pages in self._get_paginated_resources(self.pages_base_endpoint):
            if self.statuspage_ids:
                return [page for page in pages if page["id"] in self.statuspage_ids]
            return pages
        return []

    async def get_page_by_id(self, page_id: str) -> dict[str, Any]:
        response = await self.client.get(f"{self.pages_base_endpoint}/{page_id}")
        response.raise_for_status()
        return response.json()

    async def _get_resources_by_page(
        self, endpoint: str, per_page_param: str = PerPageParam.PER_PAGE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        pages = self.statuspage_ids or [page["id"] for page in await self.get_pages()]
        for page in pages:
            async for resources in self._get_paginated_resources(
                f"{self.pages_base_endpoint}/{page}/{endpoint}",
                {per_page_param: PAGE_SIZE},
            ):
                yield resources

    async def get_component_groups(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for component_groups in self._get_resources_by_page(
            ResourceKey.COMPONENT_GROUPS
        ):
            yield component_groups

    async def get_components(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for components in self._get_resources_by_page(ResourceKey.COMPONENTS):
            yield components

    async def get_incidents(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for incidents in self._get_resources_by_page(
            ResourceKey.INCIDENTS, PerPageParam.LIMIT
        ):
            yield incidents

    async def get_incident_updates(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for incidents in self.get_incidents():
            updates = [
                update
                for incident in incidents
                for update in incident.get("incident_updates", [])
            ]
            yield updates

    async def create_webhook_if_not_exists(self, page_id: str, app_host: str) -> None:
        app_host_webhook_url = f"{app_host}/integration/webhook"
        async for webhooks in self._get_paginated_resources(
            f"{self.pages_base_endpoint}/{page_id}/subscribers"
        ):
            if any(webhook["endpoint"] == app_host_webhook_url for webhook in webhooks):
                logger.info(f"Webhook already exists for page: {page_id}")
                return

        logger.info(
            f"Creating webhook subscription for page: {page_id} with endpoint: {app_host_webhook_url}"
        )
        result = await self.client.post(
            f"{self.pages_base_endpoint}/{page_id}/subscribers",
            json={"subscriber": {"endpoint": app_host_webhook_url}},
        )

        if result.status_code == 201:
            logger.info(f"Webhook created successfully for page: {page_id}")
        else:
            logger.error(
                f"Result from creating webhook for page {page_id}: ({result.status_code}) {result.text}"
            )
        return

    async def create_webhooks_for_all_pages(self, app_host: str) -> None:
        pages = self.statuspage_ids or [page["id"] for page in await self.get_pages()]
        logger.info(f"Creating webhooks for pages: {pages}")
        for page_id in pages:
            await self.create_webhook_if_not_exists(page_id, app_host)
        return
