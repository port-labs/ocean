from itertools import batched

from loguru import logger

from github.actions.external_custom_properties.abstract_executor import (
    AbstractExternalCustomPropertiesExecutor,
)
from github.actions.external_custom_properties.utils import (
    REPOSITORY_VALUES_BATCH_SIZE,
    external_property_values_endpoint,
    get_external_custom_properties_partition_key,
    group_repository_values_by_org,
    raise_external_custom_properties_action_error,
)
from github.clients.client_factory import create_github_client_for_org
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class BulkUpdateExternalCustomPropertyValuesExecutor(
    AbstractExternalCustomPropertiesExecutor
):
    """PATCH sparse updates for one external custom property across repositories."""

    ACTION_NAME = "bulk_update_external_custom_property_values"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return get_external_custom_properties_partition_key(run)

    async def execute(self, run: IntegrationRun) -> None:
        property_name = run.execution_properties.get("propertyName")
        if not property_name:
            raise InvalidActionParametersException("propertyName is required")

        default_org = run.execution_properties.get(
            "org"
        ) or ocean.integration_config.get("github_organization")
        grouped_repository_values = group_repository_values_by_org(
            run.execution_properties.get("repositoryValues"),
            default_org=default_org,
        )

        repository_count: int = sum(
            len(values) for values in grouped_repository_values.values()
        )
        request_count: int = 0

        with logger.contextualize(property_name=property_name):
            logger.info("Processing bulk external custom property update")
            for organization, repository_values in grouped_repository_values.items():
                rest_client = await create_github_client_for_org(organization)
                endpoint = external_property_values_endpoint(
                    rest_client.base_url, organization, str(property_name)
                )

                for repository_batch in batched(
                    repository_values, REPOSITORY_VALUES_BATCH_SIZE
                ):
                    request_count += 1
                    try:
                        await rest_client.make_request(
                            endpoint,
                            method="PATCH",
                            json_data={"repository_values": list(repository_batch)},
                            ignore_default_errors=False,
                        )
                    except Exception as error:
                        raise_external_custom_properties_action_error(
                            error,
                            (
                                f"bulk updating external custom property "
                                f"'{property_name}' for {organization}"
                            ),
                        )

            logger.info(
                "Successfully updated external custom property",
                repository_count=repository_count,
                organization_count=len(grouped_repository_values),
                request_count=request_count,
            )
            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message=(
                    f"Updated external custom property '{property_name}' for "
                    f"{repository_count} repositories across "
                    f"{len(grouped_repository_values)} organization(s)."
                ),
            )
