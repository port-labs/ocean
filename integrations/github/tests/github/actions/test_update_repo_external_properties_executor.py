"""Tests for UpdateRepoExternalPropertiesExecutor."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.update_repo_external_properties_executor import (
    ExternalProperty,
    UpdateRepoExternalPropertiesExecutor,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="update_repo_external_properties",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


class TestExternalPropertyFromDict:
    def test_string_value(self) -> None:
        result = ExternalProperty.from_dict({"lifecycle": "Deprecated"})
        assert result == [
            ExternalProperty(property_name="lifecycle", value="Deprecated")
        ]

    def test_none_value(self) -> None:
        result = ExternalProperty.from_dict({"prop": None})
        assert result == [ExternalProperty(property_name="prop", value=None)]

    def test_empty_string_becomes_none(self) -> None:
        result = ExternalProperty.from_dict({"prop": ""})
        assert result == [ExternalProperty(property_name="prop", value=None)]

    def test_non_string_value_coerced_to_str(self) -> None:
        result = ExternalProperty.from_dict({"count": 42, "active": True})
        assert result == [
            ExternalProperty(property_name="count", value="42"),
            ExternalProperty(property_name="active", value="True"),
        ]


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
def executor(mock_rest_client: MagicMock) -> UpdateRepoExternalPropertiesExecutor:
    with patch(
        "github.actions.abstract_github_executor.create_github_client",
        return_value=mock_rest_client,
    ):
        return UpdateRepoExternalPropertiesExecutor()


class TestUpdateRepoExternalPropertiesExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: UpdateRepoExternalPropertiesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "externalPropertiesMapping": {"lifecycle": "Deprecated"},
            }
        )

        with patch(
            "github.actions.update_repo_external_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once()
        call_kwargs = mock_rest_client.make_request.call_args
        assert "orgs/port-labs/properties/external/values" in call_kwargs.args[0]
        assert call_kwargs.kwargs["method"] == "PATCH"
        json_data = call_kwargs.kwargs["json_data"]
        assert json_data["repository_names"] == ["ocean"]
        assert json_data["properties"] == [
            {"property_name": "lifecycle", "value": "Deprecated"}
        ]

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Updated 1 external properties on port-labs/ocean.",
        )

    @pytest.mark.asyncio
    async def test_empty_mapping_skips_github_call(
        self,
        executor: UpdateRepoExternalPropertiesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "externalPropertiesMapping": {},
            }
        )

        with patch(
            "github.actions.update_repo_external_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run, success=True, message="No changes to apply."
        )

    @pytest.mark.asyncio
    async def test_missing_mapping_skips_github_call(
        self,
        executor: UpdateRepoExternalPropertiesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean"})

        with patch(
            "github.actions.update_repo_external_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run, success=True, message="No changes to apply."
        )

    @pytest.mark.asyncio
    async def test_github_http_error_raises(
        self,
        executor: UpdateRepoExternalPropertiesExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "externalPropertiesMapping": {"tier": "1"},
            }
        )

        request = httpx.Request(
            "PATCH", "https://api.github.com/orgs/port-labs/properties/external/values"
        )
        response = httpx.Response(
            422, json={"message": "Unprocessable Entity"}, request=request
        )
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "422", request=request, response=response
        )

        with pytest.raises(Exception, match="Unprocessable Entity"):
            with patch(
                "github.actions.update_repo_external_properties_executor.ocean"
            ) as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(
        self, executor: UpdateRepoExternalPropertiesExecutor
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean"})
        assert await executor._get_partition_key(run) == "port-labs/ocean"

    def test_action_name(self, executor: UpdateRepoExternalPropertiesExecutor) -> None:
        assert executor.ACTION_NAME == "update_repo_external_properties"
