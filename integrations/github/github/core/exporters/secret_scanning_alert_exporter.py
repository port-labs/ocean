from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import (
    ListSecretScanningAlertOptions,
    SingleSecretScanningAlertOptions,
)
from github.clients.http.rest_client import GithubRestClient


class RestSecretScanningAlertExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleSecretScanningAlertOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name, extras = extract_repo_params(dict(options))
        alert_number = extras["alert_number"]

        params = extras["hide_secret"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/secret-scanning/alerts/{alert_number}"
        response = await self.client.send_api_request(endpoint, params)

        logger.info(
            f"Fetched secret scanning alert with number: {alert_number} for repo: {repo_name}"
        )

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListSecretScanningAlertOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all secret scanning alerts in the repository with pagination."""

        repo_name, params = extract_repo_params(dict(options))
        if params["state"] == "all":
            params.pop("state")

        async for alerts in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/secret-scanning/alerts",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(alerts)} secret scanning alerts from repository {repo_name}"
            )
            batch_data = [enrich_with_repository(alert, repo_name) for alert in alerts]
            yield batch_data
