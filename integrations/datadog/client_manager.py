from collections import defaultdict
from typing import Any, Iterator

from loguru import logger
from pydantic import ValidationError

from datadog.client import DatadogClient
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
            org_name=credentials.org_name,
        )


class DatadogClientManager:
    """Owns the set of Datadog clients for the integration.

    Builds one client per configured organization (a single client for
    single-org installs) and resolves candidate clients for an incoming event by
    org name. The config is read once at construction, so clients — and their
    underlying HTTP connection pools — are reused across resyncs and webhook
    events rather than rebuilt on every call.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.is_multi_org: bool = bool(config.get("datadog_credential_map"))
        clients = (
            init_client_for_multi_org(config)
            if self.is_multi_org
            else [init_client_single_org(config)]
        )

        self._clients_by_org_name: dict[str | None, list[DatadogClient]] = defaultdict(
            list
        )
        for client in clients:
            self._clients_by_org_name[self._normalize_org_name(client.org_name)].append(
                client
            )

    @staticmethod
    def _normalize_org_name(org_name: str | None) -> str | None:
        return org_name.lower() if org_name is not None else None

    @property
    def clients(self) -> list[DatadogClient]:
        return [
            client
            for clients in self._clients_by_org_name.values()
            for client in clients
        ]

    def get_clients_by_org_name(self, org_name: str | None) -> list[DatadogClient]:
        """Return every client configured for the org named *org_name*.

        Single-org installs always use their sole client. Org names aren't unique,
        so multi-org installs may return several candidates; the caller tries each
        until one can fetch the event's resource. Matching is case-insensitive.
        Returns an empty list when no configured org matches.
        """
        if not self.is_multi_org:
            return self.clients

        return self._clients_by_org_name.get(self._normalize_org_name(org_name), [])


_client_manager: DatadogClientManager | None = None


def get_client_manager() -> DatadogClientManager:
    """Return the process-wide client manager, building it on first use."""
    global _client_manager
    if _client_manager is None:
        _client_manager = DatadogClientManager(ocean.integration_config)
    return _client_manager
