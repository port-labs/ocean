from typing import Any, Optional, AsyncGenerator
import httpx
from loguru import logger

from port_ocean.context.event import event


class SnykClient:
    def __init__(
        self,
        token: str,
        api_url: str,
        app_host: str | None,
        org_id: str,
        webhook_secret: str | None,
    ):
        self.token = token
        self.api_url = f"{api_url}/v1"
        self.app_host = app_host
        self.org_id = org_id
        self.rest_api_url = f"{api_url}/rest"
        self.webhook_secret = webhook_secret
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header, timeout=30)
        self.snyk_api_version = "2023-08-21"

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"token {self.token}"}

    async def _send_api_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method, url=url, params=query_params, json=json_data
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def _get_paginated_resources(
        self,
        base_url: str,
        url_path: str,
        method: str = "GET",
        data_key: str = "data",
        query_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[Any], None]:
        while url_path:
            try:
                full_url = f"{base_url}{url_path}"

                response = await self.http_client.request(
                    method=method,
                    url=full_url,
                    params={**(query_params or {}), "limit": 50},
                )
                response.raise_for_status()
                data = response.json()

                yield data[data_key]

                # Check if there is a "next" URL in the links object
                url_path = data.get("links", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def get_issues(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        def build_cache_key(project_id: str) -> str:
            return f"issues-{project_id}"

        if event.attributes.get(build_cache_key(project["id"])):
            return event.attributes[build_cache_key(project["id"])]

        url = f"{self.api_url}/org/{self.org_id}/project/{project.get('id')}/aggregated-issues"
        try:
            issues = (
                await self._send_api_request(
                    url=url,
                    method="POST",
                    query_params={"version": self.snyk_api_version},
                )
            )["issues"]
            event.attributes[build_cache_key(project["id"])] = issues
            return issues
        except Exception as e:
            logger.error(
                f"Error fetching issues for project: {project.get('id')} error: {e}"
            )
            raise

    async def get_paginated_projects(
        self,
        target_id: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if "projects" in event.attributes:
            all_projects = event.attributes["projects"]
            projects_to_yield = (
                [
                    project
                    for project in all_projects
                    if project.get("__target", {}).get("data", {}).get("id")
                    == target_id
                ]
                if target_id
                else all_projects
            )
            yield projects_to_yield
            return

        url = f"/orgs/{self.org_id}/projects"
        query_params = {
            "version": self.snyk_api_version,
            "meta.latest_issue_counts": "true",
            "expand": "target",
        }

        async for projects in self._get_paginated_resources(
            base_url=self.rest_api_url, url_path=url, query_params=query_params
        ):
            all_projects = []

            for project in projects:
                enriched_project = await self.enrich_project(project)
                all_projects.append(enriched_project)

            event.attributes.setdefault("projects", []).extend(all_projects)

            projects_to_yield = (
                [
                    project
                    for project in all_projects
                    if project.get("__target", {}).get("data", {}).get("id")
                    == target_id
                ]
                if target_id
                else all_projects
            )
            yield projects_to_yield

    async def get_single_target_by_project_id(self, project_id: str) -> dict[str, Any]:
        project = await self.get_single_project({"id": project_id})
        target_id = project.get("__target", {}).get("data", {}).get("id")

        url = f"{self.rest_api_url}/orgs/{self.org_id}/targets/{target_id}"
        query_params = {"version": f"{self.snyk_api_version}~beta"}

        response = await self._send_api_request(
            url=url, method="GET", query_params=query_params
        )

        target = response.get("data", {})
        async for projects_data_of_target in self.get_paginated_projects(
            target.get("id")
        ):
            target.setdefault("__projects", []).extend(projects_data_of_target)
        return target

    async def get_paginated_targets(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"/orgs/{self.org_id}/targets"
        query_params = {"version": f"{self.snyk_api_version}~beta"}
        async for targets in self._get_paginated_resources(
            base_url=self.rest_api_url, url_path=url, query_params=query_params
        ):
            targets_with_project_data = []
            for target_data in targets:
                async for projects_data_of_target in self.get_paginated_projects(
                    target_data.get("id")
                ):
                    target_data.setdefault("__projects", []).extend(
                        projects_data_of_target
                    )
                targets_with_project_data.append(target_data)
            yield targets_with_project_data

    async def get_single_project(self, project: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.rest_api_url}/orgs/{self.org_id}/projects/{project.get('id')}"
        query_params = {
            "version": self.snyk_api_version,
            "meta.latest_issue_counts": "true",
            "expand": "target",
        }
        response = await self._send_api_request(
            url=url, method="GET", query_params=query_params
        )
        return await self.enrich_project(response.get("data", {}))

    async def get_cached_user_details(self, user_id: str) -> dict[str, Any]:
        if (
            not user_id
        ):  ## Some projects may not have been assigned to any owner yet. In this instance, we can return an empty dict
            return {}
        cached_details = event.attributes.get(user_id)
        if cached_details:
            return cached_details

        user_details = await self._send_api_request(
            url=f"{self.api_url}/user/{user_id}"
        )
        event.attributes[user_id] = user_details
        return user_details

    async def get_cached_target_details(self, target_id: str) -> dict[str, Any]:
        cached_details = event.attributes.get(target_id)
        if cached_details:
            return cached_details

        target_details = await self._send_api_request(
            url=f"{self.rest_api_url}/orgs/{self.org_id}/targets/{target_id}",
            query_params={"version": f"{self.snyk_api_version}~beta"},
        )
        event.attributes[target_id] = target_details
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
        owner_details = await self.get_cached_user_details(owner_id)
        importer_details = await self.get_cached_user_details(importer_id)
        target_details = await self.get_cached_target_details(target_id)

        project["__owner"] = owner_details
        project["__importer"] = importer_details
        project["__target"] = target_details

        return project

    async def create_webhooks_if_not_exists(self) -> None:
        snyk_webhook_url = f"{self.api_url}/org/{self.org_id}/webhooks"
        all_subscriptions = await self._send_api_request(
            url=snyk_webhook_url, method="GET"
        )

        app_host_webhook_url = f"{self.app_host}/integration/webhook"

        for webhook in all_subscriptions.get("results", []):
            if webhook["url"] == app_host_webhook_url:
                return

        body = {"url": app_host_webhook_url, "secret": self.webhook_secret}

        await self._send_api_request(
            url=snyk_webhook_url, method="POST", json_data=body
        )
