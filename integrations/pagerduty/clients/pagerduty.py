import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from loguru import logger
from consts import ALL_EVENTS
from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.utils import http_async_client

from .utils import get_date_range_for_last_n_months

USER_KEY = "users"

MAX_CONCURRENT_REQUESTS = 10
PAGE_SIZE = 100
OAUTH_TOKEN_PREFIX = "pd"


class PagerDutyClient(OAuthClient):
    def __init__(self, token: str, api_url: str, app_host: str | None):
        super().__init__()
        self.token = token
        self.api_url = api_url
        self.app_host = app_host
        self.http_client = http_async_client
        self.http_client.headers.update(self.headers)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    @classmethod
    def from_ocean_configuration(cls) -> "PagerDutyClient":
        return cls(
            ocean.integration_config["token"],
            ocean.integration_config["api_url"],
            ocean.app.base_url,
        )

    def _get_auth_header(self, token: str) -> str:
        if token.startswith(OAUTH_TOKEN_PREFIX):
            return f"Bearer {token}"
        return f"Token token={token}"

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        try:
            auth_token = self.external_access_token
        except ValueError:
            auth_token = self.token
        request.headers["Authorization"] = self._get_auth_header(auth_token)
        return request

    @property
    def headers(self) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = self._get_auth_header(self.token)
        if self.token.startswith(OAUTH_TOKEN_PREFIX):
            headers["Accept"] = "application/vnd.pagerduty+json;version=2"
        return headers

    async def paginate_request_to_pager_duty(
        self, resource: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        offset = 0
        has_more_data = True

        while has_more_data:
            logger.debug(
                f"Fetching data for {resource} with offset: {offset} limit: {PAGE_SIZE} and params: {params}"
            )
            try:
                data = await self.send_api_request(
                    endpoint=resource,
                    query_params={
                        "offset": offset,
                        "limit": PAGE_SIZE,
                        **(params or {}),
                    },
                )
                yield data[resource]

                has_more_data = data["more"]
                if has_more_data:
                    offset += data["limit"]
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Got {e.response.status_code} status code while fetching paginated data: {str(e)}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Got an HTTP error while fetching paginated data for {resource}: {str(e)}"
                )
                raise

    async def get_single_resource(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]:
        try:
            data = await self.send_api_request(
                endpoint=f"{object_type}/{identifier}", method="GET"
            )
            return data
        except (httpx.HTTPStatusError, httpx.HTTPError) as e:
            logger.error(
                f"Error fetching data for {object_type} with identifier {identifier}: {e}"
            )
            raise

    async def create_webhooks_if_not_exists(self) -> None:
        if not self.app_host:
            logger.warning(
                "No app host provided, skipping webhook creation. "
                "Without setting up the webhook, the integration will not export live changes from PagerDuty"
            )
            return

        invoke_url = f"{self.app_host}/integration/webhook"
        async for subscriptions in self.paginate_request_to_pager_duty(
            resource="webhook_subscriptions"
        ):
            for webhook in subscriptions:
                if webhook["delivery_method"]["url"] == invoke_url:
                    return

        body = {
            "webhook_subscription": {
                "delivery_method": {
                    "type": "http_delivery_method",
                    "url": invoke_url,
                },
                "description": "Port Ocean Integration",
                "events": ALL_EVENTS,
                "filter": {"type": "account_reference"},
                "type": "webhook_subscription",
            }
        }

        try:
            await self.send_api_request(
                endpoint="webhook_subscriptions", method="POST", json_data=body
            )
        except (httpx.HTTPStatusError, httpx.HTTPError) as e:
            logger.error(f"Error creating webhook subscription: {e}")

    async def get_oncall_user(
        self, *escalation_policy_ids: str
    ) -> list[dict[str, Any]]:
        logger.info(
            f"Fetching who is oncall for escalation poilices: {','.join(escalation_policy_ids)}"
        )
        params = {
            "escalation_policy_ids[]": escalation_policy_ids,
            "include[]": "users",
        }
        oncalls = []

        async for oncall_batch in self.paginate_request_to_pager_duty(
            resource="oncalls", params=params
        ):
            logger.info(f"Received oncalls with batch size {len(oncall_batch)}")
            oncalls.extend(oncall_batch)

        return oncalls

    async def update_oncall_users(
        self, services: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        services_names = [service["name"] for service in services]
        logger.info(
            f"Fetching and matching who is on-call for {len(services)} services: {services_names}"
        )
        oncall_users = await self.get_oncall_user(
            *[service["escalation_policy"]["id"] for service in services]
        )

        for service in services:
            escalation_policy_id = service["escalation_policy"]["id"]

            service["__oncall_user"] = [
                user
                for user in oncall_users
                if user["escalation_policy"]["id"] == escalation_policy_id
            ]
        return services

    async def get_incident_analytics(self, incident_id: str) -> dict[str, Any]:
        logger.info(f"Fetching analytics for incident: {incident_id}")

        try:
            data = await self.send_api_request(
                endpoint=f"analytics/raw/incidents/{incident_id}", method="GET"
            )
            return data
        except (httpx.HTTPStatusError, httpx.HTTPError) as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                logger.debug(
                    f"Incident {incident_id} analytics data was not found, skipping..."
                )
                return {}
            else:
                logger.error(f"Error fetching incident analytics data: {e}")
                return {}

    async def paginate_cursor_request(
        self, endpoint: str, json_data: dict[str, Any], method: str = "POST"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        starting_after = None
        page = 1

        while True:
            request_data = {**json_data, "starting_after": starting_after}

            data = await self.send_api_request(
                endpoint=endpoint,
                method=method,
                json_data=request_data,
                extensions={"retryable": True},
            )

            yield data["data"]

            if not data.get("more", False):
                break

            starting_after = data.get("last")
            if not starting_after:
                break

            page += 1

    async def get_incident_analytics_by_services(
        self, service_ids: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:

        logger.info(f"Fetching analytics for services: {service_ids} for period")

        request_data = {
            "filters": {"service_ids": service_ids},
            "limit": 100,
        }

        async for analytics in self.paginate_cursor_request(
            endpoint="analytics/raw/incidents", json_data=request_data
        ):
            yield analytics

    async def get_service_analytics(
        self, service_ids: list[str], months_period: int = 3
    ) -> list[Dict[str, Any]]:
        logger.info(
            f"Fetching analytics for {len(service_ids)} services: {service_ids}"
        )
        date_ranges = get_date_range_for_last_n_months(months_period)

        body = {
            "filters": {
                "service_ids": service_ids,
                "created_at_start": date_ranges[0],
                "created_at_end": date_ranges[1],
            }
        }

        try:
            response = await self.send_api_request(
                "analytics/metrics/incidents/services",
                method="POST",
                json_data=body,
                extensions={"retryable": True},
            )
            logger.info(f"Successfully fetched analytics for services: {service_ids}")
            return response.get("data", []) if response.get("data") else []

        except (httpx.HTTPStatusError, httpx.HTTPError) as e:
            logger.error(f"Error fetching analytics for services {service_ids}: {e}")
            raise

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        extensions: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.debug(
            f"Sending API request to {method} {endpoint} with query params: {query_params}"
        )

        async with self._semaphore:
            try:
                response = await self.http_client.request(
                    method=method,
                    url=f"{self.api_url}/{endpoint}",
                    params=query_params,
                    json=json_data,
                    extensions=extensions,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.debug(
                        f"Resource not found at endpoint '{endpoint}' with params: {query_params}, method: {method}"
                    )
                    return {}
                logger.error(
                    f"HTTP error for endpoint '{endpoint}': Status code {e.response.status_code}, Method: {method}, Query params: {query_params}, Response text: {e.response.text}"
                )
                raise

    async def fetch_and_cache_users(self) -> None:
        async for users in self.paginate_request_to_pager_duty(resource=USER_KEY):
            for user in users:
                event.attributes[user["id"]] = user["email"]

    def get_cached_user(self, user_id: str) -> dict[str, Any] | None:
        return event.attributes.get(user_id)

    async def transform_user_ids_to_emails(
        self, schedules: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        await self.fetch_and_cache_users()

        for schedule in schedules:
            for user in schedule.get(USER_KEY, []):
                cached_user = self.get_cached_user(user["id"])
                if cached_user:
                    user["__email"] = cached_user
                else:
                    logger.debug(f"User ID {user['id']} not found in user cache")
        return schedules

    async def enrich_incidents_with_analytics_data(
        self, incidents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not incidents:
            return incidents
        logger.info(f"Enriching batch of {len(incidents)} incidents with analytics")
        service_ids = list({incident["service"]["id"] for incident in incidents})

        analytics_map = {}
        async for analytics_batch in self.get_incident_analytics_by_services(
            service_ids
        ):
            logger.info(f"Received analytics batch with {len(analytics_batch)} entries")
            analytics_map.update(
                {analytic["id"]: analytic for analytic in analytics_batch}
            )

        for incident in incidents:
            incident["__analytics"] = analytics_map.get(incident["id"])

        return incidents
