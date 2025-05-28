from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListReleaseOptions, SingleReleaseOptions
from github.clients.rest_client import GithubRestClient


class RestReleaseExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleReleaseOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        repo_name = options["repo_name"]
        release_id = options["release_id"]

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/releases/{release_id}"
        )
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched release with id: {release_id} for repo: {repo_name}")

        data = {"release": {**response, "name": response["name"].replace(" ", "_")}, "repo": {"name": repo_name} }
        return data

    async def get_paginated_resources[
        ExporterOptionsT: ListReleaseOptions
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all releases in the repository with pagination."""

        params: Dict[str, Any] = dict(options) if options else {}
        repo_name = params.pop("repo_name")

        async for releases in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/releases",
            params
        ):
            logger.info(
                f"Fetched batch of {len(releases)} releases from repository {repo_name}"
            )
            batch_data = [{"repo": {"name": repo_name}, "release": {**release, "name": release["name"].replace(" ", "_")}} for release in releases]
            yield batch_data 