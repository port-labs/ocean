from typing import Optional, cast
from datetime import datetime
from github.core.exporters.utils import enrich_with_repository
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from dateutil.parser import parse as parse_date


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name = options["repo_name"]
        pr_number = options["pr_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls/{pr_number}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched pull request with identifier: {repo_name}/{pr_number}")

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        params = dict(options)

        params.update({"sort": "updated", "direction": "desc"})

        repo_name = cast(str, params.pop("repo_name"))
        start_time = cast(Optional[datetime], params.pop("start_time", None))
        end_time = cast(Optional[datetime], params.pop("end_time", None))

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls"
        )

        needs_date_filtering = start_time is not None or end_time is not None

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            filtered_batch = []

            for pr in pull_requests:
                if needs_date_filtering:
                    pr_updated_at = parse_date(pr["updated_at"])

                    if (start_time and pr_updated_at < start_time) or (
                        end_time and pr_updated_at > end_time
                    ):
                        continue

                filtered_batch.append(enrich_with_repository(pr, repo_name))

            logger.info(
                f"Fetched batch of {len(filtered_batch)} pull requests from repository {repo_name}"
            )
            yield filtered_batch
