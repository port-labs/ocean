from loguru import logger

from github.actions.external_custom_properties.abstract_executor import (
    AbstractExternalCustomPropertiesExecutor,
)
from github.actions.external_custom_properties.utils import (
    external_property_values_endpoint,
    get_external_custom_properties_partition_key,
    raise_external_custom_properties_action_error,
)
from github.clients.client_factory import create_github_client_for_org
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class BulkDeleteExternalCustomPropertyValuesExecutor(
    AbstractExternalCustomPropertiesExecutor
):
    """DELETE all values for one external custom property across organizations."""

    ACTION_NAME = "bulk_delete_external_custom_property_values"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return get_external_custom_properties_partition_key(run)

    async def execute(self, run: IntegrationRun) -> None:
        property_name = run.execution_properties.get("propertyName")
        if not property_name:
            raise InvalidActionParametersException("propertyName is required")

        organizations = run.execution_properties.get("orgs")
        if not organizations:
            raise InvalidActionParametersException("orgs is required")

        with logger.contextualize(property_name=property_name):
            logger.info("Processing bulk external custom property delete")
            for organization in organizations:
                rest_client = await create_github_client_for_org(organization)
                endpoint = external_property_values_endpoint(
                    rest_client.base_url, organization, str(property_name)
                )

                try:
                    await rest_client.make_request(
                        endpoint,
                        method="DELETE",
                        ignore_default_errors=False,
                    )
                except Exception as error:
                    raise_external_custom_properties_action_error(
                        error,
                        (
                            f"bulk deleting external custom property "
                            f"'{property_name}' for {organization}"
                        ),
                    )

            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message=(
                    f"Deleted all values for external custom property "
                    f"'{property_name}' in {len(organizations)} organization(s)."
                ),
            )
