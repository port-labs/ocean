from loguru import logger

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.external_custom_properties.utils import (
    ExternalPropertyGithubValue,
    external_custom_properties_action_error_message,
)
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


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

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        organization = run.execution_properties.get("org")
        if not isinstance(organization, str):
            raise InvalidActionParametersException("org is required")
        return [await create_github_client_for_org(organization)]

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
            github_properties = [
                ExternalPropertyGithubValue(property_name=name, value=value).dict()
                for name, value in external_properties_mapping.items()
            ]

            try:
                rest_client = await create_github_client_for_org(org)
                await rest_client.make_request(
                    f"{rest_client.base_url}/orgs/{org}/properties/installations/values",
                    method="PATCH",
                    json_data={
                        "repository_names": [str(repo)],
                        "properties": github_properties,
                    },
                    ignore_default_errors=False,
                )
            except Exception as error:
                raise ActionExecutionError(
                    "Error updating external custom properties: "
                    f"{external_custom_properties_action_error_message(error)}"
                ) from error

            logger.info("Successfully updated external custom properties")
            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message=f"Updated {len(github_properties)} external custom properties on {org}/{repo}.",
            )
