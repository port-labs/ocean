from typing import cast, Optional
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from github.helpers.security_alerts import (
    enrich_security_alert_batch,
    pop_org_alert_filters,
    security_alerts_list_url,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import (
    ListSecretScanningAlertOptions,
    SingleSecretScanningAlertOptions,
)
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    paginate_with_strategy,
)

SECRET_SCANNING_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "direction": "desc"},
)


class RestSecretScanningAlertExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[ExporterOptionsT: SingleSecretScanningAlertOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:

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

    async def get_paginated_resources[ExporterOptionsT: ListSecretScanningAlertOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get secret scanning alerts with pagination (repo- or org-level)."""

        repo_name, organization, params = parse_github_options(dict(options))
        if params["state"] == "all":
            params.pop("state")

        incremental_cursor = params.pop("updated_since", None)
        allowed_repos, exclude_archived = pop_org_alert_filters(params)
        request_params = SECRET_SCANNING_INCREMENTAL.merge_params(
            params, incremental_cursor
        )
        endpoint = security_alerts_list_url(
            self.client.base_url, organization, "secret-scanning/alerts", repo_name
        )

        async for alerts in paginate_with_strategy(
            self.client.send_paginated_request(endpoint, request_params),
            cursor=incremental_cursor,
            strategy=SECRET_SCANNING_INCREMENTAL,
        ):
            scope = (
                f"repository {repo_name}"
                if repo_name
                else f"organization {organization}"
            )
            endpoint_mode = "repo-level" if repo_name else "org-level"
            logger.debug(
                f"Fetched batch of {len(alerts)} secret scanning alerts from {scope} via {endpoint_mode} endpoint"
            )
            batch = enrich_security_alert_batch(
                alerts,
                organization=organization,
                repo_name=repo_name,
                allowed_repos=allowed_repos,
                exclude_archived=exclude_archived,
            )
            if batch:
                logger.debug(f"Yielding {len(batch)} enriched alerts from {scope}")
                yield batch
