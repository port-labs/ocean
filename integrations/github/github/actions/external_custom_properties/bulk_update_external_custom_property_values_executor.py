import asyncio
from itertools import batched

from loguru import logger

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.external_custom_properties.utils import (
    REPOSITORY_VALUES_BATCH_SIZE,
    BulkOperationOutcome,
    external_custom_properties_action_error_message,
    external_property_values_endpoint,
    get_external_custom_properties_partition_key,
    group_repository_values_by_org,
)
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class BulkUpdateExternalCustomPropertyValuesExecutor(AbstractGithubExecutor):
    """PATCH sparse updates for one external custom property across repositories."""

    ACTION_NAME = "bulk_update_external_custom_property_values"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return get_external_custom_properties_partition_key(run)

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        default_org = run.execution_properties.get(
            "org"
        ) or ocean.integration_config.get("github_organization")
        grouped_repository_values = group_repository_values_by_org(
            run.execution_properties.get("repositoryValues"),
            default_org=default_org,
        )
        return [
            await create_github_client_for_org(organization)
            for organization in grouped_repository_values
        ]

    async def _patch_repository_batch(
        self,
        rest_client: AbstractGithubClient,
        endpoint: str,
        organization: str,
        repository_batch: tuple[dict[str, str | None], ...],
    ) -> BulkOperationOutcome:
        repository_names = ", ".join(
            value["repository_name"] for value in repository_batch
        )
        target = f"{organization} ({repository_names})"
        try:
            await rest_client.make_request(
                endpoint,
                method="PATCH",
                json_data={"repository_values": list(repository_batch)},
                ignore_default_errors=False,
            )
        except Exception as error:
            return BulkOperationOutcome(
                target=target,
                success=False,
                error_message=external_custom_properties_action_error_message(error),
            )

        return BulkOperationOutcome(target=target, success=True)

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

        patch_tasks: list[asyncio.Task[BulkOperationOutcome]] = []

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
                    patch_tasks.append(
                        asyncio.create_task(
                            self._patch_repository_batch(
                                rest_client,
                                endpoint,
                                organization,
                                repository_batch,
                            )
                        )
                    )

            outcomes = list(await asyncio.gather(*patch_tasks))
            failures = [outcome for outcome in outcomes if not outcome.success]
            for failure in failures:
                logger.error(
                    "Bulk external custom property update failed",
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
                    f"Updated external custom property '{property_name}': "
                    f"{len(outcomes) - len(failures)}/{len(outcomes)} request(s) succeeded."
                ),
            )
