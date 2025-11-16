"""Tests for main resync function"""

from types import SimpleNamespace
from typing import Any
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.overrides import HttpServerResourceConfig, HttpServerSelector


class TestListResponseHandling:
    """Test cases for list response auto-detection"""

    @pytest.mark.asyncio
    async def test_auto_detect_list_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that direct list responses are auto-detected and data_path is set to '.'"""
        with patch("port_ocean.context.ocean.ocean.integration.on_resync", lambda fn, kind=None: fn):
            import main

            mock_client = AsyncMock()

            mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
            mock_selector = MagicMock(spec=HttpServerSelector)
            mock_selector.method = "GET"
            mock_selector.query_params = {}
            mock_selector.headers = {}
            mock_selector.data_path = None
            mock_resource_config.selector = mock_selector

            monkeypatch.setattr(main, "event", SimpleNamespace(resource_config=mock_resource_config))

            with (
                patch("main.init_client", return_value=mock_client),
                patch("main.resolve_dynamic_endpoints") as mock_resolve,
                patch("main.ocean") as mock_ocean,
            ):
                mock_resolve.return_value = [("/api/v1/users", {})]

                direct_list_response = [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"},
                ]

                async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                    yield [direct_list_response]

                mock_client.fetch_paginated_data = mock_fetch_paginated_data

                mock_ocean.app.integration.entity_processor._search = AsyncMock(
                    return_value=direct_list_response
                )

                result = main.resync_resources("/api/v1/users")

                batch = await result.__anext__()

                assert len(batch) == 2
                assert batch[0]["id"] == 1
                assert batch[1]["id"] == 2

                mock_ocean.app.integration.entity_processor._search.assert_called()

    @pytest.mark.asyncio
    async def test_error_logged_when_not_list_and_no_data_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that error is logged when response is not a list and data_path is missing"""
        with patch("port_ocean.context.ocean.ocean.integration.on_resync", lambda fn, kind=None: fn):
            import main

            mock_client = AsyncMock()

            mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
            mock_selector = MagicMock(spec=HttpServerSelector)
            mock_selector.method = "GET"
            mock_selector.query_params = {}
            mock_selector.headers = {}
            mock_selector.data_path = None
            mock_resource_config.selector = mock_selector

            monkeypatch.setattr(main, "event", SimpleNamespace(resource_config=mock_resource_config))

            with (
                patch("main.init_client", return_value=mock_client),
                patch("main.resolve_dynamic_endpoints") as mock_resolve,
                patch("main.logger") as mock_logger,
            ):
                mock_resolve.return_value = [("/api/v1/users", {})]

                object_response = {"data": [{"id": 1, "name": "Alice"}]}

                async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                    yield [object_response]

                mock_client.fetch_paginated_data = mock_fetch_paginated_data

                result = main.resync_resources("/api/v1/users")

                batch = await result.__anext__()

                mock_logger.error.assert_called()
                error_call = mock_logger.error.call_args[0][0]
                assert "not a list" in error_call
                assert "data_path" in error_call

                assert batch == [object_response]

    @pytest.mark.asyncio
    async def test_explicit_data_path_used_when_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that explicit data_path is used when provided (no auto-detection)"""
        with patch("port_ocean.context.ocean.ocean.integration.on_resync", lambda fn, kind=None: fn):
            import main

            mock_client = AsyncMock()

            mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
            mock_selector = MagicMock(spec=HttpServerSelector)
            mock_selector.method = "GET"
            mock_selector.query_params = {}
            mock_selector.headers = {}
            mock_selector.data_path = ".data.users"
            mock_resource_config.selector = mock_selector

            monkeypatch.setattr(main, "event", SimpleNamespace(resource_config=mock_resource_config))

            with (
                patch("main.init_client", return_value=mock_client),
                patch("main.resolve_dynamic_endpoints") as mock_resolve,
                patch("main.ocean") as mock_ocean,
            ):
                mock_resolve.return_value = [("/api/v1/users", {})]

                object_response = {"data": {"users": [{"id": 1, "name": "Alice"}]}}

                async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                    yield [object_response]

                mock_client.fetch_paginated_data = mock_fetch_paginated_data

                extracted_users = [{"id": 1, "name": "Alice"}]
                mock_ocean.app.integration.entity_processor._search = AsyncMock(
                    return_value=extracted_users
                )

                result = main.resync_resources("/api/v1/users")

                batch = await result.__anext__()

                mock_ocean.app.integration.entity_processor._search.assert_called_with(
                    object_response, ".data.users"
                )

                assert len(batch) == 1
                assert batch[0]["id"] == 1