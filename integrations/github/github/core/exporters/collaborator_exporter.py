from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListCollaboratorOptions, SingleCollaboratorOptions
from github.clients.http.rest_client import GithubRestClient


class RestCollaboratorExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleCollaboratorOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        repo_name, params = extract_repo_params(dict(options))
        username = params["username"]

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/collaborators/{username}"
        )
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched collaborator with identifier: {username} from repository: {repo_name}")

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListCollaboratorOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all collaborators in the repository with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        async for collaborators in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/collaborators", params
        ):
            logger.info(
                f"Fetched batch of {len(collaborators)} collaborators from repository {repo_name}"
            )
            batch = [enrich_with_repository(collaborator, repo_name) for collaborator in collaborators]
            yield batch 