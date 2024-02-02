from port_ocean.utils import http_async_client
import httpx
from typing import Any, AsyncGenerator, Optional, Dict
from loguru import logger
from enum import StrEnum

PAGE_SIZE = 20


class ResourceKindsWithSpecialHandling(StrEnum):
    FEATURE_FLAG = "flag"
    ENVIRONMENT = "environment"


class ObjectKind(StrEnum):
    PROJECT = "project"
    AUDITLOG = "auditlog"


class LaunchDarklyClient:
    def __init__(
        self, api_token: str, launchdarkly_url: str = "https://app.launchdarkly.com"
    ):
        self.api_url = f"{launchdarkly_url}/api/v2"
        self.api_token = api_token
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"{self.api_token}",
            "Content-Type": "application/json",
        }

    async def get_paginated_resource(
        self, kind: str, resource_path: str | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        kind = kind + "s"
        url = kind if not resource_path else f"{kind}/{resource_path}"
        url = url.replace("auditlogs", "auditlog")

        params = {"limit": PAGE_SIZE}

        while url:
            try:
                response = await self.send_api_request(
                    endpoint=url, query_params=params
                )
                items = response.get("items", [])
                yield items

                if "_links" in response and "next" in response["_links"]:
                    url = response["_links"]["next"]["href"]
                else:
                    total_count = response.get("totalCount")
                    logger.info(f"Fetched {total_count} {kind} from Launchdarkly")
                    break

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"HTTP error occurred while fetching {kind} from LaunchDarkly: {e}"
                )
                raise

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"Requesting Launchdarkly data for endpoint: {endpoint}")
        try:
            endpoint = endpoint.replace("/api/v2/", "")
            url = f"{self.api_url}/{endpoint}"
            logger.info(
                f"URL: {url}, Method: {method}, Params: {query_params}, Body: {json_data}"
            )
            response = await self.http_client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()

            logger.info(f"Successfully retrieved data for endpoint: {endpoint}")

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {endpoint}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {endpoint}: {str(e)}")
            raise

    async def get_paginated_feature_flags(
        self, kind: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for items in self.get_paginated_resource(kind=ObjectKind.PROJECT):
            for project in items:
                async for flags in self.get_paginated_resource(
                    kind, resource_path=project["key"]
                ):
                    for flag in flags:
                        flag.update({"__projectKey": project["key"]})
                    yield flags

    async def get_single_feature_flag(self, data: dict) -> dict[str, Any]:
        endpoint = data["_links"]["canonical"]["href"]
        response = await self.send_api_request(endpoint)
        project_key = endpoint.split("/api/v2/flags/")[1].split("/")[0]
        response.update({"__projectKey": project_key})
        return response

    async def get_single_environment(self, data: dict) -> dict[str, Any]:
        endpoint = data["_links"]["canonical"]["href"]
        response = await self.send_api_request(endpoint)
        project_key = endpoint.split("/api/v2/projects/")[1].split("/")[0]
        response.update({"__projectKey": project_key})
        return response

    async def get_single_resource(self, data: dict) -> Dict[str, Any]:
        endpoint = data["_links"]["canonical"]
        response = await self.send_api_request(endpoint)
        return response

    async def get_paginated_environments(
        self, kind: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_paginated_resource(kind=ObjectKind.PROJECT):
            for project in projects:
                async for environments in self.get_paginated_resource(
                    ObjectKind.PROJECT, resource_path=f'{project["key"]}/{kind}s'
                ):
                    for environment in environments:
                        environment.update({"__projectKey": project["key"]})
                    yield environments

    async def create_launchdarkly_webhook(self, app_host: str) -> None:
        webhook_target_url = f"{app_host}/integration/webhook"
        notifications_response = await self.send_api_request(endpoint="webhooks")

        existing_configs = notifications_response.get("items")

        webhook_exists = any(
            config["url"] == webhook_target_url for config in existing_configs
        )
        if webhook_exists:
            logger.info("Webhook already exists")
        else:
            webhook_body = {
                "url": webhook_target_url,
                "description": "",
                "sign": False,
            }
            await self.send_api_request(
                endpoint="webhooks", method="POST", json_data=webhook_body
            )
            logger.info("Webhook created")
