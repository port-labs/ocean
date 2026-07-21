from typing import Any

import httpx
from loguru import logger

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.clients.rate_limiter.utils import is_rest_rate_limit_response
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


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


class UpdateRepoExternalCustomPropertiesExecutor(AbstractGithubExecutor):
    """
    Writes changed Port entity properties back to GitHub as repository
    external custom properties.
    """

    ACTION_NAME = "update_repo_external_custom_properties"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        """
        Repository update operations should be executed sequentially to avoid conflicts.
        We use the organization and repository as the partition key.
        """
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        return f"{org}/{repo}"

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        external_properties_mapping = run.execution_properties.get(
            "externalPropertiesMapping"
        )

        if not (org and repo):
            raise InvalidActionParametersException("org and repo are required")

        if not external_properties_mapping:
            logger.warning("No external properties to update")
            raise InvalidActionParametersException(
                "externalPropertiesMapping is required and must not be empty"
            )

        with logger.contextualize(org=org, repo=repo):
            logger.info("Processing external custom properties update")
            github_properties = external_properties_from_mapping(
                external_properties_mapping
            )

            try:
                rest_client = await self.get_rest_client(org)
                await rest_client.make_request(
                    f"{rest_client.base_url}/orgs/{org}/properties/installations/values",
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
                    if (
                        e.response.status_code == 403
                        and not is_rest_rate_limit_response(e.response)
                    ):
                        raise ActionExecutionError(
                            "Missing external custom properties write permission on the organization. "
                            "Update the integration permissions in order to enable this action."
                        )
                    try:
                        error_message = e.response.json().get("message", str(e))
                    except ValueError:
                        error_message = e.response.text or str(e)
                    logger.error(
                        "GitHub API error while updating external custom properties",
                        status_code=e.response.status_code,
                        message=error_message,
                    )
                raise ActionExecutionError(
                    f"Error updating external custom properties: {error_message}"
                )

            logger.info("Successfully updated external custom properties")
            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message=f"Updated {len(github_properties)} external custom properties on {org}/{repo}.",
            )
