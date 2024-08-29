from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from utils import ObjectKind, RESOURCE_API_VERSIONS

PAGE_SIZE = 100


class OpsGenieClient:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"GenieKey {self.token}"}

    async def get_resource_api_version(self, resource_type: ObjectKind) -> str:
        return RESOURCE_API_VERSIONS.get(resource_type, "v2")

    async def _get_single_resource(
        self,
        url: str,
        query_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.get(url=url, params=query_params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    @cache_iterator_result()
    async def get_paginated_resources(
        self, resource_type: ObjectKind, query_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}s"

        pagination_params: dict[str, Any] = {"limit": PAGE_SIZE, **(query_params or {})}
        while url:
            try:
                logger.info(
                    f"Fetching data from {url} with query params {pagination_params}"
                )
                response = await self._get_single_resource(
                    url=url, query_params=pagination_params
                )
                yield response["data"]

                url = response.get("paging", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def get_alert(self, identifier: str) -> dict[str, Any]:
        api_version = await self.get_resource_api_version(ObjectKind.ALERT)
        url = f"{self.api_url}/{api_version}/alerts/{identifier}"
        alert_data = (await self._get_single_resource(url))["data"]
        return alert_data

    async def get_oncall_team(self, identifier: str) -> dict[str, Any]:
        if not identifier:
            return {}
        logger.debug(f"Fetching on-call team with identifier: {identifier}")
        cache_key = f"{ObjectKind.TEAM}-{identifier}"

        if cache := event.attributes.get(cache_key):
            logger.debug(f"Returning on-call team {identifier} from cache")
            return cache

        api_version = await self.get_resource_api_version(ObjectKind.TEAM)
        url = f"{self.api_url}/{api_version}/teams/{identifier}"
        oncall_team = (await self._get_single_resource(url))["data"]
        event.attributes[cache_key] = oncall_team
        logger.debug(f"Fetched and cached on-call team {identifier}")
        return oncall_team

    async def get_oncall_user(self, schedule_identifier: str) -> dict[str, Any]:
        logger.debug(f"Fetching on-call user for schedule {schedule_identifier}")
        cache_key = f"{ObjectKind.SCHEDULE}-USER-{schedule_identifier}"

        if cache := event.attributes.get(cache_key):
            logger.debug(f"Returning on-call user {schedule_identifier} from cache")
            return cache

        api_version = await self.get_resource_api_version(ObjectKind.SCHEDULE)
        url = f"{self.api_url}/{api_version}/schedules/{schedule_identifier}/on-calls?flat=true"
        oncall_user = (await self._get_single_resource(url))["data"]
        event.attributes[cache_key] = oncall_user
        logger.debug(f"Fetched and cached on-call user {schedule_identifier}")
        return oncall_user

    async def get_schedule_by_team(
        self, team_identifier: str
    ) -> Optional[dict[str, Any]]:
        if not team_identifier:
            return {}
        cache_key = f"{ObjectKind.SCHEDULE}-{ObjectKind.TEAM}-{team_identifier}"
        if cache := event.attributes.get(cache_key):
            return cache
        async for schedule_batch in self.get_paginated_resources(ObjectKind.SCHEDULE):
            for schedule in schedule_batch:
                if schedule["ownerTeam"]["id"] == team_identifier:
                    event.attributes[cache_key] = schedule
                    return schedule

        return {}

    async def get_impacted_services(
        self, impacted_service_ids: list[str]
    ) -> list[dict[str, Any]]:
        if not impacted_service_ids:
            return []

        cached_services = {}
        missing_service_ids = []

        logger.info(
            f"Received request to fetch data for impacted services: {impacted_service_ids}"
        )
        # Check the cache first
        for service_id in impacted_service_ids:
            cache_key = f"{ObjectKind.SERVICE}-{service_id}"
            if cached_service := event.attributes.get(cache_key):
                cached_services[service_id] = cached_service
                logger.info(f"Fetched service {service_id} from cache")
            else:
                missing_service_ids.append(service_id)

        # If all services are cached, return them
        if not missing_service_ids:
            return [cached_services[service_id] for service_id in impacted_service_ids]

        # Fetch missing services from the API
        logger.info(f"Fetching missing services: {missing_service_ids}")
        query = f"id: ({' OR '.join(missing_service_ids)})"  # Info on service filtering can be found here: https://support.atlassian.com/opsgenie/docs/search-syntax-for-services/
        query_params = {"query": query}
        services_dict = {}

        async for service_batch in self.get_paginated_resources(
            ObjectKind.SERVICE, query_params=query_params
        ):
            for service in service_batch:
                service_id = service["id"]
                services_dict[service_id] = service
                cache_key = f"{ObjectKind.SERVICE}-{service_id}"
                event.attributes[cache_key] = service
                logger.info(f"Cached service {service_id}")

        # Combine cached and fetched services
        services_dict.update(cached_services)
        return [
            services_dict[service_id]
            for service_id in impacted_service_ids
            if service_id in services_dict
        ]
