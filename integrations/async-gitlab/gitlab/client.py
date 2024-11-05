from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError, Response
from loguru import logger
import re
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from gitlab.helpers.utils import ObjectKind, RESOURCE_API_VERSIONS
from gitlab.helpers.ratelimiter import GitLabRateLimiter

PAGE_SIZE = 100


class GitLabClient(GitLabRateLimiter):
    def __init__(self, gitlab_host: str, access_token: str) -> None:
        super().__init__(gitlab_host, access_token)
        self.token = access_token
        self.api_url = f"{gitlab_host}/api"
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"Bearer {self.token}"}

    @classmethod
    def create_from_ocean_config(cls) -> "GitLabClient":
        if cache := event.attributes.get("async_gitlab_client"):
            return cache
        github_client = cls(
            ocean.integration_config["gitlab_host"],
            ocean.integration_config["access_token"],
        )
        event.attributes["async_gitlab_client"] = github_client
        return github_client

    @staticmethod
    async def get_resource_api_version(resource_type: ObjectKind) -> str:
        return RESOURCE_API_VERSIONS.get(resource_type, "v4")

    async def update_resource(
            self,
            resource_id: str,
            resource_type: ObjectKind
    ):
        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}s/{resource_id}"

        try:
            response = await self._get_single_resource(url)
            resource = response.json()

            await ocean.register_raw(resource_type, resource)
            logger.info(f"Updated {resource_type} {resource_id} in Port")
        except Exception as e:
            logger.error(f"Failed to update {resource_type.value} {resource_id}: {str(e)}")

        return

    async def _get_single_resource(
        self,
        url: str,
        query_params: Optional[dict[str, Any]] = None,
    ) -> Response:
        try:
            self.http_client.headers.update(self.api_auth_header)
            response = await self.http_client.get(url=url, params=query_params)
            response.raise_for_status()
            return response

        except HTTPStatusError as e:
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

        pagination_params: dict[str, Any] = {"per_page": PAGE_SIZE, **(query_params or {})}
        while url:
            try:
                logger.info(
                    f"Fetching data from {url} with query params {pagination_params}"
                )
                response = await self._get_single_resource(
                    url=url, query_params=pagination_params
                )
                yield response.json()

                if response.headers.get('x-next-page'):
                    link_header = response.headers.get('link')

                    rel = "next"
                    pattern = re.compile(r'<([^>]+)>;\s*rel="%s"' % rel)
                    match = pattern.search(link_header)

                    if match:
                        url = await match.group(1)
            except HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    @cache_iterator_result()
    async def get_groups(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        limiter = await self.limiter()
        async with limiter:
            async for groups in self.get_paginated_resources(
                    resource_type=ObjectKind.GROUP
            ):
                for group in groups:
                    if 'id' in group:
                        group['id'] = str(group['id'])
                yield groups

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        limiter = await self.limiter()
        async with limiter:
            async for projects in self.get_paginated_resources(
                    resource_type=ObjectKind.PROJECT,
                    query_params={"owned": "yes"}
            ):
                for project in projects:
                    if 'id' in project:
                        project['id'] = str(project['id'])
                        project['namespace']['id'] = str(project['namespace']['id'])
                yield projects

    @cache_iterator_result()
    async def get_merge_requests(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        limiter = await self.limiter()
        async with limiter:
            async for merge_requests in self.get_paginated_resources(
                    resource_type=ObjectKind.MERGE_REQUEST
            ):
                for merge_request in merge_requests:
                    if 'id' in merge_request:
                        merge_request['id'] = str(merge_request['id'])
                        merge_request['project_id'] = str(merge_request['project_id'])
                yield merge_requests

    @cache_iterator_result()
    async def get_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        limiter = await self.limiter()
        async with limiter:
            async for issues in self.get_paginated_resources(
                    resource_type=ObjectKind.ISSUE
            ):
                for issue in issues:
                    if 'id' in issue:
                        issue['id'] = str(issue['id'])
                        issue['project_id'] = str(issue['project_id'])
                yield issues
