from typing import Any, Dict, List

from client import SonarQubeClient
from integration import SonarQubeComponentProjectSelector
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


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


def extract_metrics_from_payload(payload: Dict[str, Any]) -> list[str]:
    """Extracts a list of metrics from the qualityGate conditions in the payload."""
    return [
        condition["metric"]
        for condition in payload.get("qualityGate", {}).get("conditions", [])
    ]

def get_selector_metrics(resource_config: ResourceConfig) -> List[str]:
    """
    Extract metrics from a resource config selector if available.
    Args:
        resource_config: The resource configuration containing the selector

    Returns:
        List of metric strings, empty list if no metrics are configured
    """

    if hasattr(resource_config.selector, 'metrics'):
        return resource_config.selector.metrics
    return []