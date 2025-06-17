from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListBranchOptions, SingleBranchOptions
from github.clients.http.rest_client import GithubRestClient
from github.helpers.utils import enrich_with_repository, extract_repo_params


class RestBranchExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleBranchOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name, params = extract_repo_params(dict(options))
        branch_name = params["branch_name"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/branches/{branch_name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched branch: {branch_name} for repo: {repo_name}")

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListBranchOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all branches in the repository with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        async for branches in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/branches",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(branches)} branches from repository {repo_name}"
            )
            batch_data = [
                enrich_with_repository(branch, repo_name) for branch in branches
            ]
            yield batch_data
