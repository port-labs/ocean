from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListCodeScanningAlertOptions, SingleCodeScanningAlertOptions
from github.clients.rest_client import GithubRestClient
from github.helpers.utils import filter_options_none_values

class RestCodeScanningAlertExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleCodeScanningAlertOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        repo_name = options["repo_name"]
        alert_number = options["alert_number"]

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/code-scanning/alerts/{alert_number}"
        )
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched code scanning alert with number: {alert_number} for repo: {repo_name}")

        data = response.json()
        data["repo"] = repo_name
        return data

    async def get_paginated_resources[
        ExporterOptionsT: ListCodeScanningAlertOptions
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all code scanning alerts in the repository with pagination."""

        params: Dict[str, Any] = dict(options) if options else {}
        repo_name = params.pop("repo_name")

        params = filter_options_none_values(params)

        async for alerts in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/code-scanning/alerts",
            params
        ):
            logger.info(
                f"Fetched batch of {len(alerts)} code scanning alerts from repository {repo_name}"
            )
            batch_data = [{"repo": repo_name, **alert} for alert in alerts]
            yield batch_data 