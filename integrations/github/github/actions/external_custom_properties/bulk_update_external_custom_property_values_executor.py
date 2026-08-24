from collections.abc import Awaitable, Callable
from functools import partial
from itertools import batched

from loguru import logger

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.external_custom_properties.utils import (
    MAX_CONCURRENT_BULK_REQUESTS,
    REPOSITORY_VALUES_BATCH_SIZE,
    BulkOperationOutcome,
    RepositoryGithubValue,
    RepositoryValuesInput,
    external_custom_properties_action_error_message,
    external_property_values_endpoint,
    get_external_custom_properties_partition_key,
)
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.utils.async_iterators import throttle_batch_operation


class BulkUpdateExternalCustomPropertyValuesExecutor(AbstractGithubExecutor):
    """PATCH sparse updates for one external custom property across repositories."""

    ACTION_NAME = "bulk_update_external_custom_property_values"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return get_external_custom_properties_partition_key(run)

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        input = RepositoryValuesInput(
            org=run.execution_properties.get("org"),
            repository_values=run.execution_properties.get("repositoryValues"),
        )
        return [
            await create_github_client_for_org(organization)
            for organization in input.group_by_org().keys()
        ]

    async def _patch_repository_batch(
        self,
        rest_client: AbstractGithubClient,
        endpoint: str,
        organization: str,
        repository_batch: tuple[RepositoryGithubValue, ...],
    ) -> BulkOperationOutcome:
        repository_names = ", ".join(
            value.repository_name for value in repository_batch
        )
        target = f"{organization} ({repository_names})"
        try:
            await rest_client.make_request(
                endpoint,
                method="PATCH",
                json_data={
                    "repository_values": [value.dict() for value in repository_batch]
                },
                ignore_default_errors=False,
            )
        except Exception as error:
            return BulkOperationOutcome(
                target=target,
                success=False,
                item_count=len(repository_batch),
                error_message=external_custom_properties_action_error_message(error),
            )

        return BulkOperationOutcome(
            target=target, success=True, item_count=len(repository_batch)
        )

    async def execute(self, run: IntegrationRun) -> None:
        property_name = run.execution_properties.get("propertyName")
        if not property_name:
            raise InvalidActionParametersException("propertyName is required")

        grouped_repository_values = RepositoryValuesInput(
            org=run.execution_properties.get("org"),
            repository_values=run.execution_properties.get("repositoryValues"),
        ).group_by_org()
        patch_operations: list[Callable[[], Awaitable[BulkOperationOutcome]]] = []

        with logger.contextualize(property_name=property_name):
            logger.info("Processing bulk external custom property update")
            for organization, repository_values in grouped_repository_values.items():
                rest_client = await create_github_client_for_org(organization)
                endpoint = external_property_values_endpoint(
                    rest_client.base_url, organization, str(property_name)
                )
                patch_operations.extend(
                    partial(
                        self._patch_repository_batch,
                        rest_client,
                        endpoint,
                        organization,
                        repository_batch,
                    )
                    for repository_batch in batched(
                        repository_values, REPOSITORY_VALUES_BATCH_SIZE
                    )
                )

            outcomes = await throttle_batch_operation(
                patch_operations,
                MAX_CONCURRENT_BULK_REQUESTS,
            )
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

            succeeded_repositories = sum(
                outcome.item_count for outcome in outcomes if outcome.success
            )
            failed_repositories = sum(
                outcome.item_count for outcome in outcomes if not outcome.success
            )

            await ocean.port_client.report_run_completed(
                run,
                success=not failures,
                message=(
                    f"Updated external custom property '{property_name}': "
                    f"{succeeded_repositories} repositories succeeded, "
                    f"{failed_repositories} failed."
                ),
            )
