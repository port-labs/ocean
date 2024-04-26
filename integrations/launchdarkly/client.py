from port_ocean.utils import http_async_client
import httpx
from typing import Any, AsyncGenerator, Optional
from loguru import logger
from enum import StrEnum
import asyncio
from port_ocean.utils.cache import cache_iterator_result

PAGE_SIZE = 100


class ObjectKind(StrEnum):
    PROJECT = "project"
    AUDITLOG = "auditlog"
    FEATURE_FLAG = "flag"
    ENVIRONMENT = "environment"


class LaunchDarklyClient:
    def __init__(self, api_token: str, launchdarkly_url: str):
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
        self, kind: str, resource_path: str | None = None, page_size: int = PAGE_SIZE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        kind = kind + "s"
        url = kind if not resource_path else f"{kind}/{resource_path}"
        url = url.replace("auditlogs", ObjectKind.AUDITLOG)
        params = {"limit": page_size}

        while url:
            try:
                response = await self.send_api_request(
                    endpoint=url, query_params=params
                )
                items = response.get("items", [])
                logger.info(f"Received {kind} batch with {len(items)} items")
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
        try:
            endpoint = endpoint.replace("/api/v2/", "")
            url = f"{self.api_url}/{endpoint}"
            logger.debug(
                f"URL: {url}, Method: {method}, Params: {query_params}, Body: {json_data}"
            )
            response = await self.http_client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()

            logger.debug(f"Successfully retrieved data for endpoint: {endpoint}")

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {endpoint}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {endpoint}: {str(e)}")
            raise

    @cache_iterator_result()
    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_paginated_resource(ObjectKind.PROJECT):
            logger.info(f"Retrieved {len(projects)} projects from launchdarkly")
            yield projects

    async def get_paginated_environments(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        batch_project = [project async for project in self.get_paginated_projects()]
        tasks = [
            self.fetch_environments_for_project(project)
            for projects in batch_project
            for project in projects
        ]
        environments = await asyncio.gather(*tasks)
        for environment_batch in environments:
            yield environment_batch

    async def fetch_environments_for_project(
        self, project: dict[str, Any]
    ) -> list[dict[str, Any]]:
        environments = []
        async for environment_batch in self.get_paginated_resource(
            ObjectKind.PROJECT,
            resource_path=f'{project["key"]}/{ObjectKind.ENVIRONMENT}s',
        ):
            updated_batch = [
                {**environment, "__projectKey": project["key"]}
                for environment in environment_batch
            ]
            environments.extend(updated_batch)
        return environments

    async def get_feature_flag_status(
        self, projectKey: str, featureFlagKey: str
    ) -> dict[str, Any]:
        endpoint = f"flag-status/{projectKey}/{featureFlagKey}"
        feature_flag_status = await self.send_api_request(endpoint)
        return feature_flag_status

    async def append_feature_flag_statuses(
        self, feature_flags: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        tasks = [
            self.get_feature_flag_status(
                feature_flag["__projectKey"], feature_flag["key"]
            )
            for feature_flag in feature_flags
        ]
        statuses = await asyncio.gather(*tasks)
        for feature_flag, status in zip(feature_flags, statuses):
            feature_flag["__status"] = status
        return feature_flags

    async def get_paginated_feature_flags(
        self, sync_feature_flag_status: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        batch_project = [project async for project in self.get_paginated_projects()]
        tasks = [
            self.fetch_feature_flags_for_project(project)
            for projects in batch_project
            for project in projects
        ]
        if not sync_feature_flag_status:
            feature_flags_batches = await asyncio.gather(*tasks)
            for feature_flags in feature_flags_batches:
                yield feature_flags
        else:
            for feature_flags_batch in asyncio.as_completed(tasks):
                feature_flags = await feature_flags_batch
                updated_feature_flags = await self.append_feature_flag_statuses(
                    feature_flags
                )
                yield updated_feature_flags

    async def fetch_feature_flags_for_project(
        self, project: dict[str, Any]
    ) -> list[dict[str, Any]]:
        feature_flags = []
        async for flags_batch in self.get_paginated_resource(
            ObjectKind.FEATURE_FLAG, resource_path=project["key"]
        ):
            updated_batch = [
                {**flag, "__projectKey": project["key"]} for flag in flags_batch
            ]
            feature_flags.extend(updated_batch)
        return feature_flags

    async def create_launchdarkly_webhook(self, app_host: str) -> None:
        webhook_target_url = f"{app_host}/integration/webhook"
        notifications_response = await self.send_api_request(endpoint="webhooks")

        existing_configs = notifications_response.get("items", [])

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
