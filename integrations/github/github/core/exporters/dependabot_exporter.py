from typing import Any, Dict
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListDependabotAlertOptions, SingleDependabotAlertOptions
from github.clients.http.rest_client import GithubRestClient
from github.helpers.utils import filter_options_none_values


class RestDependabotAlertExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleDependabotAlertOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name = options["repo_name"]
        alert_number = options["alert_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/dependabot/alerts/{alert_number}"
        response = await self.client.send_api_request(endpoint)
        logger.info(
            f"Fetched Dependabot alert with number: {alert_number} for repo: {repo_name}"
        )

        response["repo"] = {"name": repo_name}
        return response

    async def get_paginated_resources[
        ExporterOptionsT: ListDependabotAlertOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Dependabot alerts in the repository with pagination."""

        params: Dict[str, Any] = dict(options)
        params["state"] = ",".join(params["state"])

        repo_name = params.pop("repo_name")
        params = filter_options_none_values(params)

        async for alerts in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/dependabot/alerts",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(alerts)} Dependabot alerts from repository {repo_name}"
            )
            batch = [{**alert, "repo": {"name": repo_name}} for alert in alerts]
            yield batch
