from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import (
    ListCodeScanningAlertOptions,
    SingleCodeScanningAlertOptions,
)
from github.clients.http.rest_client import GithubRestClient


class RestCodeScanningAlertExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleCodeScanningAlertOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name, params = extract_repo_params(dict(options))
        alert_number = params["alert_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/code-scanning/alerts/{alert_number}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched code scanning alert with number: {alert_number} for repo: {repo_name}"
        )

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListCodeScanningAlertOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all code scanning alerts in the repository with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        async for alerts in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/code-scanning/alerts",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(alerts)} code scanning alerts from repository {repo_name}"
            )
            batch_data = [enrich_with_repository(alert, repo_name) for alert in alerts]
            yield batch_data
