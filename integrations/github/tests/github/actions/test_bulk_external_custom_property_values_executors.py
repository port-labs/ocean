"""Tests for bulk external custom property values executors."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor import (
    BulkDeleteExternalCustomPropertyValuesExecutor,
)
from github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor import (
    BulkUpdateExternalCustomPropertyValuesExecutor,
)
from github.actions.external_custom_properties.utils import REPOSITORY_VALUES_BATCH_SIZE
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError


def make_run(action_name: str, execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier=action_name),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType=action_name,
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.make_request = AsyncMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def mock_port_client() -> MagicMock:
    pc = MagicMock()
    pc.post_run_log = AsyncMock()
    pc.report_run_completed = AsyncMock()
    return pc


@pytest.fixture
def bulk_update_executor(
    mock_rest_client: MagicMock,
) -> Generator[BulkUpdateExternalCustomPropertyValuesExecutor, None, None]:
    with patch(
        "github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield BulkUpdateExternalCustomPropertyValuesExecutor()


@pytest.fixture
def bulk_delete_executor(
    mock_rest_client: MagicMock,
) -> Generator[BulkDeleteExternalCustomPropertyValuesExecutor, None, None]:
    with patch(
        "github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield BulkDeleteExternalCustomPropertyValuesExecutor()


class TestBulkUpdateExternalCustomPropertyValuesExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        bulk_update_executor: BulkUpdateExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_update_external_custom_property_values",
            {
                "org": "port-labs",
                "propertyName": "lifecycle",
                "repositoryValues": [
                    {"repository_name": "ocean", "value": "Deprecated"},
                    {"repository_name": "port", "value": None},
                ],
            },
        )

        with patch(
            "github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.integration_config = {}
            await bulk_update_executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once()
        call_kwargs = mock_rest_client.make_request.call_args
        assert (
            call_kwargs.args[0]
            == "https://api.github.com/orgs/port-labs/properties/installations/values/lifecycle"
        )
        assert call_kwargs.kwargs["method"] == "PATCH"
        assert call_kwargs.kwargs["json_data"] == {
            "repository_values": [
                {"repository_name": "ocean", "value": "Deprecated"},
                {"repository_name": "port", "value": None},
            ]
        }

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message=(
                "Updated external custom property 'lifecycle' for 2 repositories "
                "across 1 organization(s)."
            ),
        )

    @pytest.mark.asyncio
    async def test_batches_repository_values(
        self,
        bulk_update_executor: BulkUpdateExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        repository_values = [
            {"repository_name": f"repo-{index}", "value": str(index)}
            for index in range(REPOSITORY_VALUES_BATCH_SIZE + 1)
        ]
        run = make_run(
            "bulk_update_external_custom_property_values",
            {
                "org": "port-labs",
                "propertyName": "tier",
                "repositoryValues": repository_values,
            },
        )

        with patch(
            "github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.integration_config = {}
            await bulk_update_executor.execute(run)

        assert mock_rest_client.make_request.await_count == 2

    @pytest.mark.asyncio
    async def test_groups_repository_values_by_org(
        self,
        bulk_update_executor: BulkUpdateExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_update_external_custom_property_values",
            {
                "propertyName": "lifecycle",
                "repositoryValues": [
                    {
                        "org": "port-labs",
                        "repository_name": "ocean",
                        "value": "Deprecated",
                    },
                    {
                        "org": "other-org",
                        "repository_name": "api",
                        "value": "production",
                    },
                ],
            },
        )

        with patch(
            "github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.integration_config = {}
            await bulk_update_executor.execute(run)

        assert mock_rest_client.make_request.await_count == 2
        endpoints = {
            call.args[0] for call in mock_rest_client.make_request.call_args_list
        }
        assert endpoints == {
            "https://api.github.com/orgs/port-labs/properties/installations/values/lifecycle",
            "https://api.github.com/orgs/other-org/properties/installations/values/lifecycle",
        }

    @pytest.mark.asyncio
    async def test_missing_repository_values_fails(
        self,
        bulk_update_executor: BulkUpdateExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_update_external_custom_property_values",
            {"org": "port-labs", "propertyName": "lifecycle"},
        )

        with pytest.raises(
            InvalidActionParametersException,
            match="repositoryValues is required and must not be empty",
        ):
            with patch(
                "github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor.ocean"
            ) as mock_ocean:
                mock_ocean.integration_config = {}
                await bulk_update_executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forbidden_raises_missing_permission_error(
        self,
        bulk_update_executor: BulkUpdateExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_update_external_custom_property_values",
            {
                "org": "port-labs",
                "propertyName": "tier",
                "repositoryValues": [
                    {"repository_name": "ocean", "value": "1"},
                ],
            },
        )
        request = httpx.Request(
            "PATCH",
            "https://api.github.com/orgs/port-labs/properties/installations/values/tier",
        )
        response = httpx.Response(403, json={"message": "Forbidden"}, request=request)
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "403", request=request, response=response
        )

        with pytest.raises(
            ActionExecutionError, match="external custom properties write"
        ):
            with patch(
                "github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor.ocean"
            ) as mock_ocean:
                mock_ocean.port_client = mock_port_client
                mock_ocean.integration_config = {}
                await bulk_update_executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(
        self, bulk_update_executor: BulkUpdateExternalCustomPropertyValuesExecutor
    ) -> None:
        run = make_run(
            "bulk_update_external_custom_property_values",
            {"org": "port-labs", "propertyName": "lifecycle"},
        )
        assert (
            await bulk_update_executor._get_partition_key(run)
            == "external_custom_properties/lifecycle"
        )


class TestBulkDeleteExternalCustomPropertyValuesExecutor:
    @pytest.mark.asyncio
    async def test_happy_path_single_org(
        self,
        bulk_delete_executor: BulkDeleteExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_delete_external_custom_property_values",
            {"orgs": ["port-labs"], "propertyName": "lifecycle"},
        )

        with patch(
            "github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.integration_config = {}
            await bulk_delete_executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once()
        call_kwargs = mock_rest_client.make_request.call_args
        assert (
            call_kwargs.args[0]
            == "https://api.github.com/orgs/port-labs/properties/installations/values/lifecycle"
        )
        assert call_kwargs.kwargs["method"] == "DELETE"
        assert "json_data" not in call_kwargs.kwargs

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message=(
                "Deleted all values for external custom property "
                "'lifecycle' in 1 organization(s)."
            ),
        )

    @pytest.mark.asyncio
    async def test_deletes_across_multiple_orgs(
        self,
        bulk_delete_executor: BulkDeleteExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_delete_external_custom_property_values",
            {
                "orgs": ["port-labs", "other-org"],
                "propertyName": "lifecycle",
            },
        )

        with patch(
            "github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.integration_config = {}
            await bulk_delete_executor.execute(run)

        assert mock_rest_client.make_request.await_count == 2
        endpoints = {
            call.args[0] for call in mock_rest_client.make_request.call_args_list
        }
        assert endpoints == {
            "https://api.github.com/orgs/port-labs/properties/installations/values/lifecycle",
            "https://api.github.com/orgs/other-org/properties/installations/values/lifecycle",
        }

    @pytest.mark.asyncio
    async def test_missing_orgs_fails(
        self,
        bulk_delete_executor: BulkDeleteExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_delete_external_custom_property_values",
            {"orgs": [], "propertyName": "lifecycle"},
        )

        with pytest.raises(
            InvalidActionParametersException,
            match="orgs is required",
        ):
            with patch(
                "github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor.ocean"
            ) as mock_ocean:
                mock_ocean.integration_config = {}
                await bulk_delete_executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_property_name_fails(
        self,
        bulk_delete_executor: BulkDeleteExternalCustomPropertyValuesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            "bulk_delete_external_custom_property_values",
            {"orgs": ["port-labs"]},
        )

        with pytest.raises(
            InvalidActionParametersException, match="propertyName is required"
        ):
            with patch(
                "github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor.ocean"
            ) as mock_ocean:
                mock_ocean.integration_config = {}
                await bulk_delete_executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partition_key(
        self, bulk_delete_executor: BulkDeleteExternalCustomPropertyValuesExecutor
    ) -> None:
        run = make_run(
            "bulk_delete_external_custom_property_values",
            {"orgs": ["port-labs"], "propertyName": "lifecycle"},
        )
        assert (
            await bulk_delete_executor._get_partition_key(run)
            == "external_custom_properties/lifecycle"
        )
