import asyncio

from loguru import logger

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.external_custom_properties.utils import (
    BulkOperationOutcome,
    external_custom_properties_action_error_message,
    external_property_values_endpoint,
    get_external_custom_properties_partition_key,
)
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class BulkDeleteExternalCustomPropertyValuesExecutor(AbstractGithubExecutor):
    """DELETE all values for one external custom property across organizations."""

    ACTION_NAME = "bulk_delete_external_custom_property_values"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return get_external_custom_properties_partition_key(run)

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        organizations: list[str] = run.execution_properties.get("orgs") or []
        return [
            await create_github_client_for_org(organization)
            for organization in organizations
        ]

    async def _delete_for_organization(
        self,
        organization: str,
        property_name: str,
    ) -> BulkOperationOutcome:
        rest_client = await create_github_client_for_org(organization)
        endpoint = external_property_values_endpoint(
            rest_client.base_url, organization, property_name
        )

        try:
            await rest_client.make_request(
                endpoint,
                method="DELETE",
                ignore_default_errors=False,
            )
        except Exception as error:
            return BulkOperationOutcome(
                target=organization,
                success=False,
                error_message=external_custom_properties_action_error_message(error),
            )

        return BulkOperationOutcome(target=organization, success=True)

    async def execute(self, run: IntegrationRun) -> None:
        property_name = run.execution_properties.get("propertyName")
        if not property_name:
            raise InvalidActionParametersException("propertyName is required")

        organizations: list[str] | None = run.execution_properties.get("orgs")
        if not organizations:
            raise InvalidActionParametersException("orgs is required")

        with logger.contextualize(property_name=property_name):
            logger.info("Processing bulk external custom property delete")
            outcomes = list(
                await asyncio.gather(
                    *(
                        self._delete_for_organization(organization, str(property_name))
                        for organization in organizations
                    )
                )
            )
            failures = [outcome for outcome in outcomes if not outcome.success]
            for failure in failures:
                logger.error(
                    "Bulk external custom property delete failed",
                    target=failure.target,
                    error=failure.error_message,
                )
                await ocean.port_client.post_run_log(
                    run, f"Failed {failure.target}: {failure.error_message}"
                )

            await ocean.port_client.report_run_completed(
                run,
                success=not failures,
                message=(
                    f"Deleted external custom property '{property_name}': "
                    f"{len(outcomes) - len(failures)}/{len(outcomes)} organization(s) succeeded."
                ),
            )
