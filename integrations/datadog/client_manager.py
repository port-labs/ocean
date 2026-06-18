from collections import defaultdict
from typing import Any, Iterator

from httpx import HTTPStatusError
from loguru import logger
from pydantic import ValidationError

from datadog.client import DatadogClient
from datadog.core.exporters import OrgExporter
from datadog.types import DatadogCredentialMap, OrgCredentials
from port_ocean.context.ocean import ocean

from datadog.exceptions import IntegrationMissingConfigError


def get_credential_map(config: dict[str, Any]) -> list[OrgCredentials]:
    credential_map_string = config.get("datadog_credential_map")
    if not credential_map_string:
        raise IntegrationMissingConfigError(
            "datadogCredentialMap (JSON string) must be provided for multi-org setups"
        )
    try:
        return DatadogCredentialMap.parse_raw(credential_map_string).__root__
    except ValidationError as e:
        logger.error(f"Failed to parse datadogCredentialMap: {e}")
        raise IntegrationMissingConfigError(f"Invalid datadogCredentialMap: {e}") from e


def init_client_single_org(config: dict[str, Any]) -> DatadogClient:
    return DatadogClient(
        config["datadog_base_url"],
        config["datadog_api_key"],
        config["datadog_application_key"],
        config["datadog_access_token"],
    )


def init_client_for_multi_org(config: dict[str, Any]) -> Iterator[DatadogClient]:
    for credentials in get_credential_map(config):
        yield DatadogClient(
            credentials.base_url or config["datadog_base_url"],
            credentials.api_key,
            credentials.app_key,
        )


class DatadogClientManager:
    """Owns the set of Datadog clients for the integration.

    For multi-org installs the configured credentials are validated against
    Datadog once at startup (``validate_and_enrich``): clients whose keys are
    rejected are dropped, and each surviving client is tagged with the org_id
    (public UUID) and org_name of the organization its keys belong to. Live events
    are then routed to candidate clients by org_id (audit trail) or org_name
    (monitor webhooks).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.is_multi_org: bool = bool(config.get("datadog_credential_map"))
        self._clients: list[DatadogClient] = (
            list(init_client_for_multi_org(config))
            if self.is_multi_org
            else [init_client_single_org(config)]
        )
        self._clients_by_org_id: dict[str, DatadogClient] = {}
        self._clients_by_org_name: dict[str, list[DatadogClient]] = {}

    @property
    def clients(self) -> list[DatadogClient]:
        return self._clients

    async def validate_credentials(self) -> None:
        """Validate each org's keys against Datadog and tag the client with the org
        id and name its keys belong to.

        Clients whose credentials are rejected (or whose org can't be resolved) are
        dropped, so resyncs and live events only run against valid keys. No-op for
        single-org installs, which keep their sole client untouched.
        """
        if not self.is_multi_org:
            return

        valid: list[DatadogClient] = []
        for client in self._clients:
            org = await self._fetch_org(client)
            if org is None:
                logger.warning(
                    f"Dropping Datadog credentials for base url '{client.api_url}': "
                    "keys are invalid or org information is unavailable",
                    application_key_prefix=client.dd_app_key[:5],
                )
                continue
            client.org_id, client.org_name = org
            valid.append(client)
            logger.info(
                f"Validated Datadog credentials for org '{client.org_name}' "
                f"(id={client.org_id})"
            )

        self._clients = valid
        self._build_indexes()

    @staticmethod
    async def _fetch_org(client: DatadogClient) -> tuple[str, str] | None:
        """Return ``(org_id, org_name)`` for *client* by querying Datadog, or None
        when the keys are rejected or no org is returned."""
        try:
            async for orgs in OrgExporter(client).get_paginated_resources():
                for org in orgs:
                    public_id, name = org.get("public_id"), org.get("name")
                    if public_id and name:
                        return public_id, name
        except HTTPStatusError as e:
            logger.warning(
                f"Datadog rejected credentials for '{client.api_url}' "
                f"({e.response.status_code})"
            )
        return None

    def _build_indexes(self) -> None:
        by_id: dict[str, DatadogClient] = {}
        by_name: dict[str, list[DatadogClient]] = defaultdict(list)
        for client in self._clients:
            org_id, org_name = client.org_id, client.org_name
            if org_id is None or org_name is None:
                continue
            by_id[org_id] = client
            by_name[self._normalize_org_name(org_name)].append(client)
        self._clients_by_org_id = by_id
        self._clients_by_org_name = by_name

    @staticmethod
    def _normalize_org_name(org_name: str) -> str:
        return org_name.lower()

    def get_client_by_org_id(self, org_id: str) -> DatadogClient | None:
        """Return the client for the org with *org_id* (audit-trail routing), or None.

        Datadog public ids are unique, so at most one client matches. Single-org
        installs always use their sole client.
        """
        if not self.is_multi_org:
            return self._clients[0]
        return self._clients_by_org_id.get(org_id)

    def get_clients_by_org_name(self, org_name: str | None) -> list[DatadogClient]:
        """Return candidate clients for the org named *org_name* (monitor routing).

        Single-org installs always use their sole client. Datadog org names are
        case-insensitive and several orgs may share a name, so multi-org installs
        may return multiple candidates; the caller tries each in turn.
        """
        if not self.is_multi_org:
            return self._clients
        if org_name is None:
            return []
        return self._clients_by_org_name.get(self._normalize_org_name(org_name), [])


_client_manager: DatadogClientManager | None = None


def get_client_manager() -> DatadogClientManager:
    """Return the process-wide client manager, building it on first use."""
    global _client_manager
    if _client_manager is None:
        _client_manager = DatadogClientManager(ocean.integration_config)
    return _client_manager
