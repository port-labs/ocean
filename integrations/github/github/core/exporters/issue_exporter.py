from typing import cast
from github.helpers.utils import enrich_with_repository, parse_github_options
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleIssueOptions, ListIssueOptions
from github.clients.http.base_client import AbstractGithubClient


class RestIssueExporter(AbstractGithubExporter[AbstractGithubClient]):

    async def get_resource[
        ExporterOptionsT: SingleIssueOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name, organization, params = parse_github_options(dict(options))
        issue_number = params["issue_number"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/issues/{issue_number}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched issue {issue_number} from {repo_name} from {organization}"
        )

        return enrich_with_repository(response, cast(str, repo_name))

    async def get_paginated_resources[
        ExporterOptionsT: ListIssueOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:

        repo_name, organization, params = parse_github_options(dict(options))

        async for issues in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/issues",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(issues)} issues from repository {repo_name} from {organization}"
            )
            batch = [
                enrich_with_repository(issue, cast(str, repo_name)) for issue in issues
            ]
            yield batch
