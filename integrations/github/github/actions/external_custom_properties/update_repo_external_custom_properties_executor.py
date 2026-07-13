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


class UpdateRepoExternalCustomPropertiesExecutor(AbstractGithubExecutor):
    """PATCH-merge external custom properties on a single repository."""

    ACTION_NAME = "update_repo_external_custom_properties"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        return f"{org}/{repo}" if org and repo else None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        external_properties_mapping = run.execution_properties.get(
            "externalPropertiesMapping"
        )

        if not (org and repo):
            raise InvalidActionParametersException("org and repo are required")

        if not external_properties_mapping:
            raise InvalidActionParametersException(
                "externalPropertiesMapping is required and must not be empty"
            )

        github_properties = external_custom_properties_from_mapping(
            external_properties_mapping
        )

        try:
            await self.rest_client.make_request(
                f"{self.rest_client.base_url}/orgs/{org}/properties/installations/values",
                method="PATCH",
                json_data={
                    "repository_names": [str(repo)],
                    "properties": github_properties,
                },
                ignore_default_errors=False,
            )
        except Exception as e:
            error_message = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                if e.response.status_code == 403 and not is_rate_limit_response(
                    e.response
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
                f"Error updating external custom properties: {error_message}"
            )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=(
                f"Updated {len(github_properties)} external custom properties "
                f"on {org}/{repo}."
            ),
        )
