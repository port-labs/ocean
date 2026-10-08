from typing import cast
from github.core.exporters.base_alert_exporter import BaseSecurityAlertExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import RAW_ITEM
from loguru import logger
from github.core.options import SingleSecretScanningAlertOptions
from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy

SECRET_SCANNING_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "direction": "desc"},
)


class RestSecretScanningAlertExporter(BaseSecurityAlertExporter):

    @property
    def alert_type_name(self) -> str:
        return "secret scanning"

    @property
    def resource_path(self) -> str:
        return "secret-scanning/alerts"

    @property
    def incremental_strategy(self) -> ClientSideCutoffStrategy:
        return SECRET_SCANNING_INCREMENTAL

    def prepare_request_params(self, params: dict) -> None:
        """Remove state param if it's 'all' (not supported by API)."""
        if params.get("state") == "all":
            params.pop("state")

    async def get_resource[ExporterOptionsT: SingleSecretScanningAlertOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM | None:

        repo_name, organization, params = parse_github_options(dict(options))
        alert_number = params.pop("alert_number")

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/secret-scanning/alerts/{alert_number}"
        response = await self.client.send_api_request(endpoint, params)
        if not response:
            logger.warning(
                f"No secret scanning alert found with number: {alert_number} in repository: {repo_name} from {organization}"
            )
            return None

        logger.info(
            f"Fetched secret scanning alert with number: {alert_number} for repo: {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )
