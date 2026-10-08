from typing import cast
from github.core.exporters.base_alert_exporter import BaseSecurityAlertExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import RAW_ITEM
from loguru import logger
from github.core.options import SingleDependabotAlertOptions
from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy

DEPENDABOT_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "direction": "desc"},
)


class RestDependabotAlertExporter(BaseSecurityAlertExporter):

    @property
    def alert_type_name(self) -> str:
        return "Dependabot"

    @property
    def resource_path(self) -> str:
        return "dependabot/alerts"

    @property
    def incremental_strategy(self) -> ClientSideCutoffStrategy:
        return DEPENDABOT_INCREMENTAL

    def prepare_request_params(self, params: dict) -> None:
        """Join state list as comma-separated string for API request."""
        params["state"] = ",".join(params["state"])

    async def get_resource[ExporterOptionsT: SingleDependabotAlertOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM | None:

        repo_name, organization, params = parse_github_options(dict(options))
        alert_number = params["alert_number"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/dependabot/alerts/{alert_number}"
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No Dependabot alert found with number: {alert_number} in repository: {repo_name} from {organization}"
            )
            return None

        logger.info(
            f"Fetched Dependabot alert with number: {alert_number} for repo: {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )
