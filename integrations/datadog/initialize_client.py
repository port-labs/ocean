import json
from typing import Any, Iterator

from loguru import logger
from datadog.client import DatadogClient
from port_ocean.context.ocean import ocean

from datadog.exceptions import IntegrationMissingConfigError


def get_credential_map(config: dict[str, Any]) -> dict[str, Any]:
    credential_map_string = config.get("datadog_credential_map")
    if credential_map_string:
        try:
            parsed = json.loads(credential_map_string)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse datadogCredentialMap: {e}")
            raise IntegrationMissingConfigError(
                f"Invalid JSON in datadogCredentialMap: {e}"
            ) from e

    raise IntegrationMissingConfigError(
        "datadogCredentialMap (JSON string) must be provided when isMultiOrg is enabled"
    )


def init_client_single_org(config: dict[str, Any]) -> DatadogClient:
    return DatadogClient(
        config["datadog_base_url"],
        config["datadog_api_key"],
        config["datadog_application_key"],
        config["datadog_access_token"],
    )


def init_client_for_multi_org(config: dict[str, Any]) -> Iterator[DatadogClient]:
    credential_map = get_credential_map(config)
    for org_id, credentials in credential_map.items():
        try:
            api_key = credentials["datadogApiKey"]
            app_key = credentials["datadogApplicationKey"]
        except (KeyError, TypeError) as e:
            raise IntegrationMissingConfigError(
                f"datadogCredentialMap entry for org '{org_id}' must include "
                "'datadogApiKey' and 'datadogApplicationKey'"
            ) from e
        yield DatadogClient(
            config["datadog_base_url"],
            api_key,
            app_key,
            org_id=org_id,
        )


class DatadogClientManager:
    """Owns the set of Datadog clients for the integration.

    Builds one client per configured organization (a single client for
    single-org installs) and resolves the right client for an incoming event by
    org id. The config is read once at construction, so clients — and their
    underlying HTTP connection pools — are reused across resyncs and webhook
    events rather than rebuilt on every call.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.is_multi_org: bool = config["is_multi_org"]
        if self.is_multi_org:
            self._clients = list(init_client_for_multi_org(config))
        else:
            self._clients = [init_client_single_org(config)]
        self._clients_by_org: dict[str | None, DatadogClient] = {
            client.org_id: client for client in self._clients
        }

    @property
    def clients(self) -> list[DatadogClient]:
        return self._clients

    def get_client_for_org(self, org_id: str | None) -> DatadogClient | None:
        """Return the client responsible for *org_id*.

        Single-org installs always use their sole client. Multi-org installs
        match the event's org id against the configured credential map, returning
        None (so callers can skip the event) when nothing matches.
        """
        if not self.is_multi_org:
            return self._clients[0]

        client = self._clients_by_org.get(org_id)
        if client is None:
            logger.warning(
                f"No Datadog client configured for org_id '{org_id}'; skipping event"
            )
        return client


_client_manager: DatadogClientManager | None = None


def get_client_manager() -> DatadogClientManager:
    """Return the process-wide client manager, building it on first use."""
    global _client_manager
    if _client_manager is None:
        _client_manager = DatadogClientManager(ocean.integration_config)
    return _client_manager


def init_client() -> Iterator[DatadogClient]:
    """Yield every configured Datadog client (one per org), reusing cached clients."""
    return iter(get_client_manager().clients)
