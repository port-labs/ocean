import asyncio
from enum import StrEnum
from typing import Any, Optional, AsyncGenerator

import httpx
from httpx import Timeout
from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client


class CacheKeys(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    TARGET = "target"
    USER = "user"
    GROUP = "group"
    ORGANIZATION = "organization"


class SnykClient:
    def __init__(
        self,
        token: str,
        api_url: str,
        app_host: str | None,
        organization_id: str | None,
        group_ids: str | None,
        webhook_secret: str | None,
    ):
        self.token = token
        self.api_url = f"{api_url}/v1"
        self.app_host = app_host
        self.organization_id = organization_id
        self.group_ids = group_ids
        self.rest_api_url = f"{api_url}/rest"
        self.webhook_secret = webhook_secret
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)
        self.http_client.timeout = Timeout(30)
        self.snyk_api_version = "2023-08-21"

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"token {self.token}"}

    async def _send_api_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        version: str | None = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        query_params = {
            **(query_params or {}),
            **({"version": version} if version is not None else {}),
        }
        try:
            response = await self.http_client.request(
                method=method, url=url, params=query_params, json=json_data
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an error while sending a request to {method} {url} with query_params: {query_params}, "
                f"version: {version}, json: {json_data}. "
                f"Got HTTP error with status code: {e.response.status_code} and response: {e.response.text}"
            )
            raise

    async def _get_paginated_resources(
        self,
        url_path: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[Any], None]:
        while url_path:
            try:
                data = await self._send_api_request(
                    url=f"{self.rest_api_url}{url_path}",
                    method=method,
                    query_params={**(query_params or {}), "limit": 50},
                )

                yield data.get("data", [])

                # Check if there is a "next" URL in the links object
                url_path = data.get("links", {}).get("next")
                query_params = {}  # Reset query params for the next iteration
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def get_issues(self, org_id: str, project_id: str) -> list[dict[str, Any]]:
        cache_key = f"{CacheKeys.ISSUE}-{project_id}"
        # We cache the issues for each project in the event attributes as in the same resync events we may need to fetch the issues multiple times for aggregations
        if cache := event.attributes.get(cache_key):
            return cache

        url = f"{self.api_url}/org/{org_id}/project/{project_id}/aggregated-issues"
        issues = (
            await self._send_api_request(
                url=url,
                method="POST",
                version=self.snyk_api_version,
            )
        ).get("issues", [])

        event.attributes[cache_key] = issues
        return issues

    def _get_projects_by_target(
        self,
        all_projects: list[dict[str, Any]],
        target_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return (
            [
                project
                for project in all_projects
                if project.get("__target", {}).get("data", {}).get("id") == target_id
            ]
            if target_id
            else all_projects
        )

    async def get_paginated_projects(
        self,
        target_id: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if CacheKeys.PROJECT in event.attributes:
            all_projects = event.attributes[CacheKeys.PROJECT]
            projects_to_yield = self._get_projects_by_target(
                all_projects, target_id=target_id
            )
            yield projects_to_yield
            return

        all_organizations = await self.get_organizations_in_groups()
        for org in all_organizations:
            logger.info(f"Fetching paginated projects for organization: {org['id']}")
            url = f"/orgs/{org['id']}/projects"
            query_params = {
                "version": self.snyk_api_version,
                "meta.latest_issue_counts": "true",
                "expand": "target",
            }

            async for projects in self._get_paginated_resources(
                url_path=url, query_params=query_params
            ):
                all_projects = []

                for project in projects:
                    enriched_project = await self.enrich_project(project)
                    all_projects.append(enriched_project)

                event.attributes.setdefault(CacheKeys.PROJECT, []).extend(all_projects)

                projects_to_yield = self._get_projects_by_target(
                    all_projects, target_id=target_id
                )
                yield projects_to_yield

    async def get_single_target_by_project_id(
        self, org_id: str, project_id: str
    ) -> dict[str, Any]:
        project = await self.get_single_project(org_id, project_id)
        target_id = project["__target"]["data"]["id"]

        url = f"{self.rest_api_url}/orgs/{org_id}/targets/{target_id}"

        response = await self._send_api_request(
            url=url, method="GET", version=f"{self.snyk_api_version}~beta"
        )

        if not response:
            return {}

        target = response["data"]
        async for projects_data_of_target in self.get_paginated_projects(target["id"]):
            target.setdefault("__projects", []).extend(projects_data_of_target)
        return target

    async def get_paginated_targets(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        all_organizations = await self.get_organizations_in_groups()
        for org in all_organizations:
            logger.info(f"Fetching paginated targets for organization: {org['id']}")

            url = f"/orgs/{org['id']}/targets"
            target_api_version = "2024-05-23"
            query_params = {"version": f"{target_api_version}~beta"}
            async for targets in self._get_paginated_resources(
                url_path=url, query_params=query_params
            ):
                targets_with_project_data = []
                for target_data in targets:
                    async for projects_data_of_target in self.get_paginated_projects(
                        target_data["id"]
                    ):
                        target_data.setdefault("__projects", []).extend(
                            projects_data_of_target
                        )
                    targets_with_project_data.append(target_data)
                yield targets_with_project_data

    async def get_single_project(self, org_id: str, project_id: str) -> dict[str, Any]:
        if CacheKeys.PROJECT in event.attributes:
            all_projects = event.attributes[CacheKeys.PROJECT]
            project = next(
                (
                    project
                    for project in all_projects
                    if project.get("id") == project_id
                ),
                None,
            )
            if project:
                return project

        url = f"{self.rest_api_url}/orgs/{org_id}/projects/{project_id}"
        query_params = {
            "meta.latest_issue_counts": "true",
            "expand": "target",
        }
        response = await self._send_api_request(
            url=url,
            method="GET",
            query_params=query_params,
            version=self.snyk_api_version,
        )

        project = await self.enrich_project(response.get("data", {}))

        event.attributes.setdefault(CacheKeys.PROJECT, []).append(project)

        return project

    async def _get_user_details(self, user_id: str | None) -> dict[str, Any]:
        if (
            not user_id
        ):  ## Some projects may not have been assigned to any owner yet. In this instance, we can return an empty dict
            return {}
        cached_details = event.attributes.get(f"{CacheKeys.USER}-{user_id}")
        if cached_details:
            return cached_details

        try:
            user_details = await self._send_api_request(
                url=f"{self.api_url}/user/{user_id}"
            )

            if not user_details:
                return {}

            event.attributes[f"{CacheKeys.USER}-{user_id}"] = user_details
            return user_details
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"user {user_id} not was not found, skipping...")
                return {}
            else:
                raise

    async def _get_target_details(self, org_id: str, target_id: str) -> dict[str, Any]:
        cached_details = event.attributes.get(f"{CacheKeys.TARGET}-{target_id}")
        if cached_details:
            return cached_details

        target_details = await self._send_api_request(
            url=f"{self.rest_api_url}/orgs/{org_id}/targets/{target_id}",
            version=f"{self.snyk_api_version}~beta",
        )
        event.attributes[f"{CacheKeys.TARGET}-{target_id}"] = target_details
        return target_details

    async def enrich_project(self, project: dict[str, Any]) -> dict[str, Any]:
        owner_id = (
            project.get("relationships", {}).get("owner", {}).get("data", {}).get("id")
        )
        importer_id = (
            project.get("relationships", {})
            .get("importer", {})
            .get("data", {})
            .get("id")
        )
        target_id = (
            project.get("relationships", {}).get("target", {}).get("data", {}).get("id")
        )
        organization_id = project["relationships"]["organization"]["data"]["id"]

        tasks = [
            self._get_user_details(owner_id),
            self._get_user_details(importer_id),
            self._get_target_details(organization_id, target_id),
        ]

        owner_details, importer_details, target_details = await asyncio.gather(*tasks)

        project["__owner"] = owner_details
        project["__importer"] = importer_details
        project["__target"] = target_details

        return project

    async def create_webhooks_if_not_exists(self) -> None:
        all_organizations = await self.get_organizations_in_groups()
        for org in all_organizations:
            logger.info(f"Fetching webhooks for organization: {org['id']}")

            snyk_webhook_url = f"{self.api_url}/org/{org['id']}/webhooks"
            all_subscriptions = await self._send_api_request(
                url=snyk_webhook_url, method="GET"
            )

            app_host_webhook_url = f"{self.app_host}/integration/webhook"

            for webhook in all_subscriptions["results"]:
                if webhook["url"] == app_host_webhook_url:
                    return

            body = {"url": app_host_webhook_url, "secret": self.webhook_secret}
            logger.info(f"Creating webhook subscription for organization: {org['id']}")
            await self._send_api_request(
                url=snyk_webhook_url, method="POST", json_data=body
            )

    async def get_all_organizations(self) -> list[dict[str, Any]]:
        url = f"{self.api_url}/orgs"
        response = await self._send_api_request(url=url)
        organizations = response.get("orgs", [])

        logger.info(f"Fetched {len(organizations)} organizations for the given token.")
        return organizations

    async def get_organizations_in_groups(self) -> list[Any]:
        # Check if the result is already cached
        if cache := event.attributes.get(CacheKeys.GROUP):
            logger.info("Fetched Snyk organizations from the cache")
            return cache

        all_organizations = await self.get_all_organizations()

        if self.organization_id:
            logger.info(f"Specified organization ID: {self.organization_id}")
            matching_organization = [
                org for org in all_organizations if org["id"] == self.organization_id
            ]

            if matching_organization:
                event.attributes[CacheKeys.GROUP] = matching_organization
                return matching_organization
            else:
                logger.warning(
                    f"Specified organization ID '{self.organization_id}' not found in the fetched organizations."
                )
                return []

        elif self.group_ids:
            groups = self.group_ids.split(",")

            logger.info(
                f"Found {len(groups)} groups to filter. Group IDs: {str(groups)}. Getting all organizations associated with these groups"
            )

            matching_organizations_in_groups = [
                org
                for org in all_organizations
                if org.get("group") and org["group"].get("id") in groups
            ]

            logger.info(
                f"Fetched {len(matching_organizations_in_groups)} organizations for the given groups."
            )

            event.attributes[CacheKeys.GROUP] = matching_organizations_in_groups
            return matching_organizations_in_groups
        else:
            logger.info(
                "Integration config did not specify any group(s) or organizationId to filter. Getting all organizations linked to the provided Snyk token"
            )

            event.attributes[CacheKeys.GROUP] = all_organizations
            return all_organizations
