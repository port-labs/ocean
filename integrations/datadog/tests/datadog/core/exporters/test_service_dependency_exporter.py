import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import ServiceDependencyExporter
from datadog.core.exporters.service_dependency_exporter import (
    FETCH_WINDOW_TIME_IN_SECONDS,
    GetServiceDependencyOptions,
    ListServiceDependencyOptions,
)


@pytest.fixture
def resource_config() -> Any:
    mock_resource_config = MagicMock()
    mock_resource_config.selector.environment = "prod"
    mock_resource_config.selector.start_time = 2.5
    return mock_resource_config


@pytest.mark.asyncio
async def test_get_service_dependencies(
    mock_datadog_client: DatadogClient, resource_config: Any
) -> None:
    expected_return_value: dict[str, Any] = {
        "service_a": {"calls": ["service_b", "service_c"]},
        "service_b": {"calls": ["service_o"]},
        "service_c": {"calls": ["service_o"]},
        "service_o": {"calls": []},
    }

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = expected_return_value

        exporter = ServiceDependencyExporter(mock_datadog_client)
        dependencies: list[dict[str, Any]] = []
        end_time = int(time.time())
        async for dependency_batch in exporter.get_paginated_resources(
            ListServiceDependencyOptions(
                env=resource_config.selector.environment,
                start_time=resource_config.selector.start_time,
            )
        ):
            dependencies.extend(dependency_batch)

        assert len(dependencies) == 4
        items: list[dict[str, Any]] = [
            {"name": name, **details} for name, details in expected_return_value.items()
        ]
        assert dependencies == items

        parsed_start_time = int(
            time.time()
            - (FETCH_WINDOW_TIME_IN_SECONDS * resource_config.selector.start_time)
        )
        mock_request.assert_called_with(
            f"{mock_datadog_client.api_url}/api/v1/service_dependencies",
            params={
                "env": resource_config.selector.environment,
                "start": parsed_start_time,
                "end": end_time,
            },
        )


@pytest.mark.asyncio
async def test_get_single_service_dependency_returns_none_when_not_found(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {}
        exporter = ServiceDependencyExporter(mock_datadog_client)

        result = await exporter.get_resource(
            GetServiceDependencyOptions(env="prod", start_time=1, service_id="svc-1")
        )

    assert result is None
