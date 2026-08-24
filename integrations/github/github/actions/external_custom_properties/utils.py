from collections import defaultdict
from typing import Any
from urllib.parse import quote

import httpx
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from github.clients.rate_limiter.utils import is_rest_rate_limit_response
from github.helpers.exceptions import InvalidActionParametersException

REPOSITORY_VALUES_BATCH_SIZE = 100


def get_external_custom_properties_partition_key(run: IntegrationRun) -> str:
    return f"external_custom_properties/{run.execution_properties.get('propertyName')}"


def external_properties_from_mapping(
    external_properties_mapping: dict[str, Any],
) -> list[dict[str, str | None]]:
    return [
        {
            "property_name": name,
            "value": None if value is None or value == "" else str(value),
        }
        for name, value in external_properties_mapping.items()
    ]


def external_property_values_endpoint(
    base_url: str, org: str, property_name: str
) -> str:
    encoded_property_name = quote(str(property_name), safe=".")
    return (
        f"{base_url}/orgs/{org}/properties/installations/values/"
        f"{encoded_property_name}"
    )


def group_repository_values_by_org(
    repository_values: Any,
    *,
    default_org: str | None,
) -> dict[str, list[dict[str, str | None]]]:
    if not repository_values:
        raise InvalidActionParametersException(
            "repositoryValues is required and must not be empty"
        )
    if not isinstance(repository_values, list):
        raise InvalidActionParametersException("repositoryValues must be an array")

    grouped: dict[str, list[dict[str, str | None]]] = defaultdict(list)

    for index, item in enumerate(repository_values):
        if not isinstance(item, dict):
            raise InvalidActionParametersException(
                f"repositoryValues[{index}] must be an object"
            )

        organization: str | None = item.get("org") or default_org
        if not organization:
            raise InvalidActionParametersException(
                f"repositoryValues[{index}].org is required when top level org "
                "is not configured"
            )

        repository_name: str | None = item.get("repository_name")
        if not repository_name:
            raise InvalidActionParametersException(
                f"repositoryValues[{index}].repository_name is required"
            )
        if "value" not in item:
            raise InvalidActionParametersException(
                f"repositoryValues[{index}].value is required"
            )

        grouped[str(organization)].append(
            {
                "repository_name": str(repository_name),
                "value": item["value"],
            }
        )

    return grouped


def raise_external_custom_properties_action_error(
    error: Exception, action_description: str
) -> None:
    error_message = str(error)
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 403 and not is_rest_rate_limit_response(
            error.response
        ):
            raise ActionExecutionError(
                "Missing external custom properties write permission on the organization. "
                "Update the integration permissions in order to enable this action."
            ) from error
        try:
            error_message = error.response.json().get("message", str(error))
        except ValueError:
            error_message = error.response.text or str(error)
    raise ActionExecutionError(
        f"Error {action_description}: {error_message}"
    ) from error
