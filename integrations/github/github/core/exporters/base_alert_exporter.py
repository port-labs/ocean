from abc import ABC, abstractmethod
from typing import TypeVar

from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.security_alerts import (
    enrich_security_alert_batch,
    pop_org_alert_filters,
    security_alerts_list_url,
)
from github.helpers.utils import parse_github_options
from loguru import logger
from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy, paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from github.clients.http.rest_client import GithubRestClient

ExporterOptionsT = TypeVar("ExporterOptionsT")


class BaseSecurityAlertExporter(AbstractGithubExporter[GithubRestClient], ABC):
    """Base class for security alert exporters (dependabot, code-scanning, secret-scanning)."""

    @property
    @abstractmethod
    def alert_type_name(self) -> str:
        """Human-readable alert type (e.g., 'Dependabot', 'code scanning')."""

    @property
    @abstractmethod
    def resource_path(self) -> str:
        """API resource path (e.g., 'dependabot/alerts', 'code-scanning/alerts')."""

    @property
    @abstractmethod
    def incremental_strategy(self) -> ClientSideCutoffStrategy:
        """Incremental sync strategy for this alert type."""

    def prepare_request_params(self, params: dict) -> None:
        """Override to customize params before API request. Called after pop_org_alert_filters."""

    async def get_paginated_resources(
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get alerts with pagination (repo- or org-level). Handles common pagination logic."""

        repo_name, organization, params = parse_github_options(dict(options))
        incremental_cursor = params.pop("updated_since", None)
        allowed_repos, exclude_archived = pop_org_alert_filters(params)

        self.prepare_request_params(params)

        request_params = self.incremental_strategy.merge_params(params, incremental_cursor)
        endpoint = security_alerts_list_url(
            self.client.base_url, organization, self.resource_path, repo_name
        )

        async for alerts in paginate_with_strategy(
            self.client.send_paginated_request(endpoint, request_params),
            cursor=incremental_cursor,
            strategy=self.incremental_strategy,
        ):
            scope = (
                f"repository {repo_name}"
                if repo_name
                else f"organization {organization}"
            )
            endpoint_mode = "repo-level" if repo_name else "org-level"
            logger.debug(
                f"Fetched batch of {len(alerts)} {self.alert_type_name} alerts from {scope} via {endpoint_mode} endpoint"
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
