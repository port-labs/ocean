from typing import Any

from client import SonarQubeClient
from integration import SonarQubeComponentProjectSelector
from port_ocean.context.ocean import ocean


def produce_component_params(
    client: SonarQubeClient,
    selector: SonarQubeComponentProjectSelector,
) -> dict[str, Any]:
    component_query_params: dict[str, Any] = {}
    if client.organization_id:
        component_query_params["organization"] = client.organization_id

    ## Handle query_params based on environment
    if client.is_onpremise and selector:
        component_query_params.update(selector.generate_request_params())
    return component_query_params


def init_sonar_client() -> SonarQubeClient:
    return SonarQubeClient(
        ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
        ocean.integration_config["sonar_api_token"],
        ocean.integration_config.get("sonar_organization_id"),
        ocean.integration_config.get("app_host"),
        ocean.integration_config["sonar_is_on_premise"],
    )
