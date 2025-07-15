from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name, params = extract_repo_params(dict(options))
        pr_number = params["pr_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls/{pr_number}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched pull request with identifier: {repo_name}/{pr_number}")

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls"
        )

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_name}"
            )
            batch = [enrich_with_repository(pr, repo_name) for pr in pull_requests]
            yield batch
