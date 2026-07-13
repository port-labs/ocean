"""Tests for ReplaceRepositoriesExternalCustomPropertiesExecutor."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.actions.external_custom_properties.replace_repositories_external_custom_properties_executor import (
    PROPERTIES_BATCH_SIZE,
    REPOSITORIES_BATCH_SIZE,
    ReplaceRepositoriesExternalCustomPropertiesExecutor,
)
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(
            identifier="replace_repositories_external_custom_properties"
        ),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="replace_repositories_external_custom_properties",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.make_request = AsyncMock()
    return client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> ReplaceRepositoriesExternalCustomPropertiesExecutor:
    with patch(
        "github.actions.abstract_github_executor.create_github_client",
        return_value=mock_rest_client,
    ):
        return ReplaceRepositoriesExternalCustomPropertiesExecutor()


class TestReplaceRepositoriesExternalCustomPropertiesExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self, executor: ReplaceRepositoriesExternalCustomPropertiesExecutor, mock_rest_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "repositories": [
                    {
                        "org": "port-labs",
                        "repo": "ocean",
                        "externalPropertiesMapping": {"lifecycle": "Deprecated"},
                    }
                ]
            }
        )

        with patch(
            "github.actions.external_custom_properties.replace_repositories_external_custom_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = MagicMock(report_run_completed=AsyncMock())
            mock_ocean.integration_config = {}
            await executor.execute(run)

        call_kwargs = mock_rest_client.make_request.call_args
        assert call_kwargs.kwargs["method"] == "PUT"
        assert call_kwargs.kwargs["json_data"]["repositories"] == [
            {
                "name": "ocean",
                "properties": [{"property_name": "lifecycle", "value": "Deprecated"}],
            }
        ]

    @pytest.mark.asyncio
    async def test_batches_repositories_and_properties(
        self, executor: ReplaceRepositoriesExternalCustomPropertiesExecutor, mock_rest_client: MagicMock
    ) -> None:
        properties = {
            f"prop-{index}": str(index)
            for index in range(PROPERTIES_BATCH_SIZE + 5)
        }
        repositories = [
            {
                "org": "port-labs",
                "repo": f"repo-{index}",
                "externalPropertiesMapping": {"tier": str(index)},
            }
            for index in range(REPOSITORIES_BATCH_SIZE + 5)
        ]
        run = make_run(
            {
                "repositories": [
                    {
                        "org": "port-labs",
                        "repo": "ocean",
                        "externalPropertiesMapping": properties,
                    },
                    *repositories,
                ]
            }
        )

        with patch(
            "github.actions.external_custom_properties.replace_repositories_external_custom_properties_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = MagicMock(report_run_completed=AsyncMock())
            mock_ocean.integration_config = {}
            await executor.execute(run)

        assert mock_rest_client.make_request.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_input_fails(
        self, executor: ReplaceRepositoriesExternalCustomPropertiesExecutor, mock_rest_client: MagicMock
    ) -> None:
        with pytest.raises(
            InvalidActionParametersException,
            match="repositories is required and must not be empty",
        ):
            with patch(
                "github.actions.external_custom_properties.replace_repositories_external_custom_properties_executor.ocean"
            ):
                await executor.execute(make_run({"repositories": []}))

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partition_key_is_global(
        self, executor: ReplaceRepositoriesExternalCustomPropertiesExecutor
    ) -> None:
        run = make_run({"repositories": [{"org": "port-labs", "repo": "ocean", "externalPropertiesMapping": {"a": "1"}}]})
        assert (
            await executor._get_partition_key(run)
            == "replace_repositories_external_custom_properties"
        )
