from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleIssueOptions, ListIssueOptions
from github.clients.http.base_client import AbstractGithubClient


class RestIssueExporter(AbstractGithubExporter[AbstractGithubClient]):

    async def get_resource[
        ExporterOptionsT: SingleIssueOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name = options["repo_name"]
        issue_number = options["issue_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/issues/{issue_number}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched issue with identifier: {repo_name}/{issue_number}")

        response["repository"] = {"name": repo_name}
        return response

    async def get_paginated_resources[
        ExporterOptionsT: ListIssueOptions
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:

        params: Dict[str, Any] = dict(options) if options else {}
        repo_name = params.pop("repo_name")

        async for issues in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/issues",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(issues)} issues from repository {repo_name}"
            )
            batch = [{**issue, "repository": {"name": repo_name}} for issue in issues]
            yield batch
