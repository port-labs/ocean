from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from pydantic.v1 import BaseModel, validator
from port_ocean.core.models import IntegrationRun

from github.clients.rate_limiter.utils import is_rest_rate_limit_response
from github.helpers.exceptions import InvalidActionParametersException

REPOSITORY_VALUES_BATCH_SIZE = 100


@dataclass(frozen=True)
class BulkOperationOutcome:
    target: str
    success: bool
    error_message: str | None = None


class _GithubExternalPropertyValue(BaseModel):
    value: str | None

    @validator("value", pre=True)
    def normalize_value(cls, value: Any) -> str | None:
        # Only None and "" clear the value; 0 and other falsy values are valid.
        if value is None or value == "":
            return None
        return str(value)


class RepositoryGithubValue(_GithubExternalPropertyValue):
    repository_name: str


class ExternalPropertyGithubValue(_GithubExternalPropertyValue):
    property_name: str


def get_external_custom_properties_partition_key(run: IntegrationRun) -> str:
    return f"external_custom_properties/{run.execution_properties.get('propertyName')}"


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
    if repository_values is None or repository_values == []:
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

        organization = item.get("org") or default_org
        if not organization:
            raise InvalidActionParametersException(
                f"repositoryValues[{index}].org is required when top level org "
                "is not configured"
            )

        repository_name = item.get("repository_name")
        if not repository_name:
            raise InvalidActionParametersException(
                f"repositoryValues[{index}].repository_name is required"
            )
        if "value" not in item:
            raise InvalidActionParametersException(
                f"repositoryValues[{index}].value is required"
            )

        grouped[str(organization)].append(
            RepositoryGithubValue(
                repository_name=str(repository_name),
                value=item["value"],
            ).dict()
        )

    return grouped


def external_custom_properties_action_error_message(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 403 and not is_rest_rate_limit_response(
            error.response
        ):
            return (
                "Missing external custom properties write permission on the organization. "
                "Update the integration permissions in order to enable this action."
            )
        try:
            return error.response.json().get("message", str(error))
        except ValueError:
            return error.response.text or str(error)
    return str(error)
