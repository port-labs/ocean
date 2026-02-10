"""Tests for main resync function and endpoint exporter"""

from types import SimpleNamespace
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, cast
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from integration import HttpServerResourceConfig, HttpServerSelector


async def mock_resolve_single_endpoint() -> (
    AsyncGenerator[List[tuple[str, Dict[str, str]]], None]
):
    """Helper mock generator that yields a single batch with one endpoint"""
    yield [("/api/v1/users", {})]


async def mock_process_endpoints(
    endpoints: List[tuple[str, Dict[str, str]]],
    fetch_fn: Any,
    concurrency_limit: int = 10,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Mock concurrent processing that just calls fetch_fn for each endpoint"""
    for endpoint, path_params in endpoints:
        async for batch in fetch_fn(endpoint, path_params):
            yield batch


class TestListResponseHandling:
    """Test cases for list response auto-detection"""

    @pytest.mark.asyncio
    async def test_auto_detect_list_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that direct list responses are auto-detected and data_path is set to '.'"""
        with patch(
            "port_ocean.context.ocean.ocean.integration.on_resync",
            lambda fn, kind=None: fn,
        ):
            import main

            mock_client = AsyncMock()

            mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
            mock_selector = MagicMock(spec=HttpServerSelector)
            mock_selector.method = "GET"
            mock_selector.query_params = {}
            mock_selector.headers = {}
            mock_selector.data_path = None
            mock_resource_config.selector = mock_selector

            monkeypatch.setattr(
                main, "event", SimpleNamespace(resource_config=mock_resource_config)
            )

            with (
                patch(
                    "main.get_client",
                    return_value=mock_client,
                ),
                patch(
                    "custom.core.exporters.resource_exporter.resolve_dynamic_endpoints",
                    return_value=mock_resolve_single_endpoint(),
                ),
                patch(
                    "custom.core.exporters.resource_exporter.process_endpoints_concurrently",
                    side_effect=mock_process_endpoints,
                ),
                patch(
                    "custom.helpers.utils.JQEntityProcessorSync"
                ) as mock_jq_sync,
            ):
                direct_list_response = [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"},
                ]

                async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                    yield [direct_list_response]

                mock_client.fetch_paginated_data = mock_fetch_paginated_data

                mock_jq_sync._search.return_value = direct_list_response

                assert main.resync_resources is not None
                result = main.resync_resources("/api/v1/users")
                result_iter = cast(AsyncIterator[List[Dict[str, Any]]], result)

                batch = await result_iter.__anext__()

                assert len(batch) == 2
                assert batch[0]["id"] == 1
                assert batch[1]["id"] == 2

                mock_jq_sync._search.assert_called()

    @pytest.mark.asyncio
    async def test_warning_logged_when_not_list_and_no_data_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that warning is logged when response is not a list and data_path is missing"""
        with patch(
            "port_ocean.context.ocean.ocean.integration.on_resync",
            lambda fn, kind=None: fn,
        ):
            import main

            mock_client = AsyncMock()

            mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
            mock_selector = MagicMock(spec=HttpServerSelector)
            mock_selector.method = "GET"
            mock_selector.query_params = {}
            mock_selector.headers = {}
            mock_selector.data_path = None
            mock_resource_config.selector = mock_selector

            monkeypatch.setattr(
                main, "event", SimpleNamespace(resource_config=mock_resource_config)
            )

            with (
                patch(
                    "main.get_client",
                    return_value=mock_client,
                ),
                patch(
                    "custom.core.exporters.resource_exporter.resolve_dynamic_endpoints",
                    return_value=mock_resolve_single_endpoint(),
                ),
                patch(
                    "custom.core.exporters.resource_exporter.process_endpoints_concurrently",
                    side_effect=mock_process_endpoints,
                ),
                patch(
                    "custom.core.exporters.resource_exporter.logger"
                ) as mock_logger,
            ):
                object_response = {"data": [{"id": 1, "name": "Alice"}]}

                async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                    yield [object_response]

                mock_client.fetch_paginated_data = mock_fetch_paginated_data

                assert main.resync_resources is not None
                result = main.resync_resources("/api/v1/users")
                result_iter = cast(AsyncIterator[List[Dict[str, Any]]], result)

                batch = await result_iter.__anext__()

                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert "not a list" in warning_call
                assert "data_path" in warning_call

                assert batch == [object_response]

    @pytest.mark.asyncio
    async def test_explicit_data_path_used_when_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that explicit data_path is used when provided (no auto-detection)"""
        with patch(
            "port_ocean.context.ocean.ocean.integration.on_resync",
            lambda fn, kind=None: fn,
        ):
            import main

            mock_client = AsyncMock()

            mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
            mock_selector = MagicMock(spec=HttpServerSelector)
            mock_selector.method = "GET"
            mock_selector.query_params = {}
            mock_selector.headers = {}
            mock_selector.data_path = ".data.users"
            mock_resource_config.selector = mock_selector

            monkeypatch.setattr(
                main, "event", SimpleNamespace(resource_config=mock_resource_config)
            )

            with (
                patch(
                    "main.get_client",
                    return_value=mock_client,
                ),
                patch(
                    "custom.core.exporters.resource_exporter.resolve_dynamic_endpoints",
                    return_value=mock_resolve_single_endpoint(),
                ),
                patch(
                    "custom.core.exporters.resource_exporter.process_endpoints_concurrently",
                    side_effect=mock_process_endpoints,
                ),
                patch(
                    "custom.helpers.utils.JQEntityProcessorSync"
                ) as mock_jq_sync,
            ):
                object_response = {"data": {"users": [{"id": 1, "name": "Alice"}]}}

                async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                    yield [object_response]

                mock_client.fetch_paginated_data = mock_fetch_paginated_data

                extracted_users = [{"id": 1, "name": "Alice"}]
                mock_jq_sync._search.return_value = extracted_users

                assert main.resync_resources is not None
                result = main.resync_resources("/api/v1/users")
                result_iter = cast(AsyncIterator[List[Dict[str, Any]]], result)

                batch = await result_iter.__anext__()

                mock_jq_sync._search.assert_called_with(object_response, ".data.users")

                assert len(batch) == 1
                assert batch[0]["id"] == 1
