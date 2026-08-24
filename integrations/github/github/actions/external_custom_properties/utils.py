from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import Field
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


class ExternalPropertyGithubValue(_GithubExternalPropertyValue):
    property_name: str


class RepositoryGithubValue(_GithubExternalPropertyValue):
    repository_name: str


class RepositoryValuesInput(BaseModel):

    class RepositoryValueInput(RepositoryGithubValue):
        org: str | None = None

    org: str | None = None
    repository_values: list[RepositoryValueInput] = Field(min_items=1)

    def group_by_org(self) -> dict[str, list[RepositoryGithubValue]]:
        grouped: dict[str, list[RepositoryGithubValue]] = defaultdict(list)
        for value in self.repository_values:
            organization: str | None = value.org or self.org
            if not organization:
                raise InvalidActionParametersException(
                    f"No org provided for repository {value.repository_name}"
                )
            grouped[organization].append(
                RepositoryGithubValue(
                    repository_name=value.repository_name,
                    value=value.value,
                )
            )
        return grouped


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
