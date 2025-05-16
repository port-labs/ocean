from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.clients.base_client import AbstractGithubClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter


class PullRequestExporter(AbstractGithubExporter[AbstractGithubClient]):

    async def get_resource[
        PROptionsT: SinglePullRequestOptions
    ](self, options: OptionT,) -> RAW_ITEM:
        repo_name = options["repo_name"]
        pr_number = options["pr_number"]

        endpoint = f"repos/{self.client.organization}/{repo_name}/pulls/{pr_number}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched pull request with identifier: {repo_name}/{pr_number}")

        return response.json()

    async def get_paginated_resources[
        PROptionsT: ListPullRequestOptions
    ](self, options: PROptionsT,) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name = options["repo_name"]

        async for pull_requests in self.client.send_paginated_request(
            f"repos/{self.client.organization}/{repo_name}/pulls",
            {"state": options["state"]},
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_name}"
            )
            yield pull_requests
