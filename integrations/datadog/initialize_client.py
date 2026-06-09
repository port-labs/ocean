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


def init_client() -> Iterator[DatadogClient]:
    config = ocean.integration_config
    if config["is_multi_org"]:
        yield from init_client_for_multi_org(config)
    else:
        yield init_client_single_org(config)


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
