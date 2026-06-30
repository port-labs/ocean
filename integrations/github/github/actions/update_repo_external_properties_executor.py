from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun


class ExternalProperty(BaseModel):
    property_name: str
    value: str | None

    @staticmethod
    def from_dict(
        external_properties_mapping: dict[str, Any],
    ) -> list["ExternalProperty"]:
        """
        Convert a flat {name: value} dict into the GitHub properties array:
            [ExternalProperty(property_name="...", value="...")]
        """
        return [
            ExternalProperty(
                property_name=name,
                value=None if value is None or value == "" else str(value),
            )
            for name, value in external_properties_mapping.items()
        ]


class PatchExternalPropertiesBody(BaseModel):
    repository_names: list[str]
    properties: list[ExternalProperty]


class UpdateRepoExternalPropertiesExecutor(AbstractGithubExecutor):
    """
    Writes changed Port entity properties back to GitHub as repository
    external / custom properties.
    """

    ACTION_NAME = "update_repo_external_properties"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        org: str = run.execution_properties.get("org")
        repo: str = run.execution_properties.get("repo")
        external_properties_mapping: dict[str, Any] = run.execution_properties.get(
            "externalPropertiesMapping"
        )

        with logger.contextualize(org=org, repo=repo):
            logger.info("Processing external property update")

            if not external_properties_mapping:
                logger.info(
                    "No properties changes detected — nothing to push to GitHub"
                )
                await ocean.port_client.report_run_completed(
                    run, success=True, message="No changes to apply."
                )
                return

            github_properties = ExternalProperty.from_dict(external_properties_mapping)

            try:
                await self.rest_client.make_request(
                    f"{self.rest_client.base_url}/orgs/{org}/properties/external/values",
                    method="PATCH",
                    json_data=PatchExternalPropertiesBody(
                        repository_names=[repo],
                        properties=github_properties,
                    ).dict(),
                    ignore_default_errors=False,
                )
            except Exception as e:
                error_message = str(e)
                if isinstance(e, httpx.HTTPStatusError):
                    error_message = e.response.json().get("message", str(e))
                    logger.error(
                        "GitHub API error while updating external properties",
                        status_code=e.response.status_code,
                        message=error_message,
                    )
                raise Exception(f"Error updating external properties: {error_message}")

            logger.info("Successfully updated external properties")
            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message=f"Updated {len(github_properties)} external properties on {org}/{repo}.",
            )
