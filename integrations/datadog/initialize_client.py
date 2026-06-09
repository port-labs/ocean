import json
from typing import Any, Iterator

from loguru import logger
from datadog.client import DatadogClient
from port_ocean.context.ocean import ocean

from datadog.exceptions import IntegrationMissingConfigError


def get_credential_map(config: dict[str, Any]) -> dict[str, Any]:
    cluster_conf_string = config.get("cluster_conf_mapping_string")
    if cluster_conf_string:
        try:
            parsed = json.loads(cluster_conf_string)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cluster_conf_mapping_string: {e}")
            raise IntegrationMissingConfigError(
                f"Invalid JSON in cluster_conf_mapping_string: {e}"
            ) from e

    raise IntegrationMissingConfigError(
        "Either clusterConfMapping (object) or clusterConfMappingString (JSON string) must be provided"
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
    for k, v in credential_map.items():
        yield DatadogClient(
            config["datadog_base_url"],
            v["datadog_api_key"],
            v["datadog_application_key"],
            org_id=k,
        )
