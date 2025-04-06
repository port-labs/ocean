from typing import Any, Dict

from client import SonarQubeClient
from integration import SonarQubeComponentProjectSelector


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
