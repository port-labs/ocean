from typing import Any, Iterator

from loguru import logger
from pydantic import ValidationError

from datadog.client import DatadogClient
from datadog.types import DatadogCredentialMap, OrgCredentials
from port_ocean.context.ocean import ocean

from datadog.exceptions import IntegrationMissingConfigError


def get_credential_map(config: dict[str, Any]) -> dict[str, OrgCredentials]:
    credential_map_string = config.get("datadog_credential_map")
    if not credential_map_string:
        raise IntegrationMissingConfigError(
            "datadogCredentialMap (JSON string) must be provided for multi-org setups"
        )
    try:
        return DatadogCredentialMap.parse_raw(credential_map_string).__root__
    except ValidationError as e:
        logger.error(f"Failed to parse datadogCredentialMap: {e}")
        raise IntegrationMissingConfigError(
            f"Invalid datadogCredentialMap: {e}"
        ) from e


def init_client_single_org(config: dict[str, Any]) -> DatadogClient:
    return DatadogClient(
        config["datadog_base_url"],
        config["datadog_api_key"],
        config["datadog_application_key"],
        config["datadog_access_token"],
    )


def init_client_for_multi_org(config: dict[str, Any]) -> Iterator[DatadogClient]:
    credential_map = get_credential_map(config)
    for org_uuid, credentials in credential_map.items():
        yield DatadogClient(
            config["datadog_base_url"],
            credentials.api_key,
            credentials.app_key,
            org_uuid=org_uuid,
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
        # Multi-org is inferred from the presence of a credential map rather than a
        # separate flag: a configured map means multiple orgs, its absence a single one.
        self.is_multi_org: bool = bool(config.get("datadog_credential_map"))
        clients = (
            init_client_for_multi_org(config)
            if self.is_multi_org
            else [init_client_single_org(config)]
        )
        self._clients_by_org_uuid: dict[str | None, DatadogClient] = {
            client.org_uuid: client for client in clients
        }

    @property
    def clients(self) -> list[DatadogClient]:
        return list(self._clients_by_org_uuid.values())

    def get_client_by_org_uuid(self, org_uuid: str | None) -> DatadogClient | None:
        """Return the client responsible for the org with *org_uuid*.

        Single-org installs always use their sole client. Multi-org installs match
        the event's org uuid (the credential-map key) against the configured orgs,
        returning None (so callers can skip the event) when nothing matches. The
        uuid is globally unique and survives org renames, unlike the org name.
        """
        if not self.is_multi_org:
            return next(iter(self._clients_by_org_uuid.values()))

        client = self._clients_by_org_uuid.get(org_uuid)
        if client is None:
            logger.warning(
                f"No Datadog client configured for org uuid '{org_uuid}'; skipping event"
            )
        return client


_client_manager: DatadogClientManager | None = None


def get_client_manager() -> DatadogClientManager:
    """Return the process-wide client manager, building it on first use."""
    global _client_manager
    if _client_manager is None:
        _client_manager = DatadogClientManager(ocean.integration_config)
    return _client_manager
