from typing import cast
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListReleaseOptions, SingleReleaseOptions
from github.clients.http.rest_client import GithubRestClient
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)


class RestReleaseExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleReleaseOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name, organization, params = parse_github_options(dict(options))
        release_id = params["release_id"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/releases/{release_id}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched release with id: {release_id} for repo: {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListReleaseOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all releases in the repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))

        async for releases in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/releases",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(releases)} releases from repository {repo_name} from {organization}"
            )
            batch_data = [
                enrich_with_organization(
                    enrich_with_repository(release, cast(str, repo_name)), organization
                )
                for release in releases
            ]
            yield batch_data
