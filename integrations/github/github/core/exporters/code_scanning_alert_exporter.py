from typing import cast, Optional
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import (
    ListCodeScanningAlertOptions,
    SingleCodeScanningAlertOptions,
)
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    paginate_with_strategy,
)

CODE_SCANNING_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "direction": "desc"},
)


class RestCodeScanningAlertExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[ExporterOptionsT: SingleCodeScanningAlertOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:

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

    async def get_paginated_resources[ExporterOptionsT: ListCodeScanningAlertOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all code scanning alerts in the repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))
        incremental_cursor = params.pop("incremental_cursor", None)
        request_params = CODE_SCANNING_INCREMENTAL.merge_params(
            params, incremental_cursor
        )

        async for alerts in paginate_with_strategy(
            self.client.send_paginated_request(
                f"{self.client.base_url}/repos/{organization}/{repo_name}/code-scanning/alerts",
                request_params,
            ),
            cursor=incremental_cursor,
            strategy=CODE_SCANNING_INCREMENTAL,
        ):
            logger.info(
                f"Fetched batch of {len(alerts)} code scanning alerts from repository {repo_name} from {organization}"
            )
            batch_data = [
                enrich_with_organization(
                    enrich_with_repository(alert, cast(str, repo_name)), organization
                )
                for alert in alerts
            ]
            yield batch_data
