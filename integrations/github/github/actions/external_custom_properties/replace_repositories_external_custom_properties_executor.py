from collections import defaultdict
from itertools import batched
from typing import Any

import httpx

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.external_custom_properties.utils import (
    external_custom_properties_from_mapping,
)
from github.clients.rate_limiter.utils import is_rate_limit_response
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

REPOSITORIES_BATCH_SIZE = 20
PROPERTIES_BATCH_SIZE = 100


class ReplaceRepositoriesExternalCustomPropertiesExecutor(AbstractGithubExecutor):
    """PUT-replace external custom properties on multiple repositories (unsent props are removed)."""

    ACTION_NAME = "replace_repositories_external_custom_properties"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        # ponytail: global lock for replace; per-org keys if concurrent orgs matter
        return self.ACTION_NAME

    async def execute(self, run: IntegrationRun) -> None:
        items = run.execution_properties.get("repositories")
        if not items:
            raise InvalidActionParametersException(
                "repositories is required and must not be empty"
            )
        if not isinstance(items, list):
            raise InvalidActionParametersException("repositories must be an array")

        default_org = ocean.integration_config.get("github_organization")
        updates_by_org: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise InvalidActionParametersException(
                    f"item {index} must be an object"
                )

            repo = item.get("repo")
            mapping = item.get("externalPropertiesMapping")
            org = item.get("org") or default_org

            if not org:
                raise InvalidActionParametersException(
                    "org is required when github_organization is not configured"
                )
            if not repo:
                raise InvalidActionParametersException(f"item {index}.repo is required")
            if not mapping:
                raise InvalidActionParametersException(
                    f"item {index}.externalPropertiesMapping is required and must not be empty"
                )

            updates_by_org[org].append(
                {
                    "name": str(repo),
                    "properties": external_custom_properties_from_mapping(mapping),
                }
            )

        property_count = 0
        for org, repositories in updates_by_org.items():
            expanded: list[dict[str, Any]] = []
            for repository in repositories:
                property_count += len(repository["properties"])
                for batch in batched(repository["properties"], PROPERTIES_BATCH_SIZE):
                    expanded.append(
                        {"name": repository["name"], "properties": list(batch)}
                    )

            for batch in batched(expanded, REPOSITORIES_BATCH_SIZE):
                try:
                    await self.rest_client.make_request(
                        f"{self.rest_client.base_url}/orgs/{org}/properties/installations/values",
                        method="PUT",
                        json_data={"repositories": list(batch)},
                        ignore_default_errors=False,
                    )
                except Exception as e:
                    error_message = str(e)
                    if isinstance(e, httpx.HTTPStatusError):
                        if (
                            e.response.status_code == 403
                            and not is_rate_limit_response(e.response)
                        ):
                            raise ActionExecutionError(
                                "Missing external custom properties write permission on the organization. "
                                "Update the integration permissions in order to enable this action."
                            )
                        try:
                            error_message = e.response.json().get("message", str(e))
                        except ValueError:
                            error_message = e.response.text or str(e)
                    raise ActionExecutionError(
                        f"Error replacing external custom properties for {org}: {error_message}"
                    )

        repo_count = sum(len(repos) for repos in updates_by_org.values())
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=(
                f"Replaced {property_count} external custom properties "
                f"across {repo_count} repositories in {len(updates_by_org)} organization(s)."
            ),
        )
