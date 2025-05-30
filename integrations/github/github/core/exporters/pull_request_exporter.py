from typing import Any, Dict
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name = options["repo_name"]
        pr_number = options["pr_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls/{pr_number}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched pull request with identifier: {repo_name}/{pr_number}")

        response["__repository"] = repo_name
        return response

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        params = dict(options)
        repo_name = params.pop("repo_name")

        async for pull_requests in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_name}"
            )
            batch = [{**pr, "__repository": repo_name} for pr in pull_requests]
            yield batch
