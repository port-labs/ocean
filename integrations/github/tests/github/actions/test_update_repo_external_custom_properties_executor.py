"""Tests for UpdateRepoExternalCustomPropertiesExecutor."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.external_custom_properties.utils import (
    external_custom_properties_from_mapping,
)
from github.actions.external_custom_properties.update_repo_external_custom_properties_executor import (
    UpdateRepoExternalCustomPropertiesExecutor,
)
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="update_repo_external_custom_properties"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="update_repo_external_custom_properties",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


class TestExternalPropertiesFromMapping:
    def test_string_value(self) -> None:
        assert external_custom_properties_from_mapping({"lifecycle": "Deprecated"}) == [
            {"property_name": "lifecycle", "value": "Deprecated"}
        ]


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.make_request = AsyncMock()
    return client


@pytest.fixture
def executor(mock_rest_client: MagicMock) -> UpdateRepoExternalCustomPropertiesExecutor:
    with patch(
        "github.actions.abstract_github_executor.create_github_client",
        return_value=mock_rest_client,
    ):
        return UpdateRepoExternalCustomPropertiesExecutor()


class TestUpdateRepoExternalCustomPropertiesExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: UpdateRepoExternalCustomPropertiesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "externalPropertiesMapping": {"lifecycle": "Deprecated"},
            }
        )

        with patch(
            "github.actions.external_custom_properties.update_repo_external_custom_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = MagicMock(report_run_completed=AsyncMock())
            mock_ocean.integration_config = {}
            await executor.execute(run)

        call_kwargs = mock_rest_client.make_request.call_args
        assert call_kwargs.kwargs["method"] == "PATCH"
        assert call_kwargs.kwargs["json_data"] == {
            "repository_names": ["ocean"],
            "properties": [{"property_name": "lifecycle", "value": "Deprecated"}],
        }

    @pytest.mark.asyncio
    async def test_falls_back_to_integration_org(
        self,
        executor: UpdateRepoExternalCustomPropertiesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "repo": "ocean",
                "externalPropertiesMapping": {"lifecycle": "Deprecated"},
            }
        )

        with patch(
            "github.actions.external_custom_properties.update_repo_external_custom_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = MagicMock(report_run_completed=AsyncMock())
            mock_ocean.integration_config = {"github_organization": "port-labs"}
            await executor.execute(run)

        assert "orgs/port-labs/properties/installations/values" in (
            mock_rest_client.make_request.call_args.args[0]
        )

    @pytest.mark.asyncio
    async def test_missing_org_without_config_fails(
        self,
        executor: UpdateRepoExternalCustomPropertiesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "repo": "ocean",
                "externalPropertiesMapping": {"lifecycle": "Deprecated"},
            }
        )

        with pytest.raises(
            InvalidActionParametersException,
            match="org is required when github_organization is not configured",
        ):
            with patch(
                "github.actions.external_custom_properties.update_repo_external_custom_properties_executor.ocean"
            ) as mock_ocean:
                mock_ocean.integration_config = {}
                await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forbidden_raises(
        self,
        executor: UpdateRepoExternalCustomPropertiesExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "externalPropertiesMapping": {"tier": "1"},
            }
        )
        request = httpx.Request(
            "PATCH",
            "https://api.github.com/orgs/port-labs/properties/installations/values",
        )
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "403",
            request=request,
            response=httpx.Response(
                403, json={"message": "Forbidden"}, request=request
            ),
        )

        with pytest.raises(
            ActionExecutionError, match="external custom properties write"
        ):
            with patch(
                "github.actions.external_custom_properties.update_repo_external_custom_properties_executor.ocean"
            ):
                await executor.execute(run)
