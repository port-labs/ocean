from typing import cast
from github.core.exporters.base_alert_exporter import BaseSecurityAlertExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import RAW_ITEM
from loguru import logger
from github.core.options import SingleCodeScanningAlertOptions
from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy

CODE_SCANNING_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "direction": "desc"},
)


class RestCodeScanningAlertExporter(BaseSecurityAlertExporter):

    @property
    def alert_type_name(self) -> str:
        return "code scanning"

    @property
    def resource_path(self) -> str:
        return "code-scanning/alerts"

    @property
    def incremental_strategy(self) -> ClientSideCutoffStrategy:
        return CODE_SCANNING_INCREMENTAL

    async def get_resource[ExporterOptionsT: SingleCodeScanningAlertOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM | None:

        repo_name, organization, params = parse_github_options(dict(options))
        alert_number = params["alert_number"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/code-scanning/alerts/{alert_number}"
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No code scanning alert found with number: {alert_number} in repository: {repo_name} from {organization}"
            )
            return None

        logger.info(
            f"Fetched code scanning alert with number: {alert_number} for repo: {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )
