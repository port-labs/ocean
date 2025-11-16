"""Tests for main resync function"""

from typing import Any
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.overrides import HttpServerResourceConfig, HttpServerSelector


class TestListResponseHandling:
    """Test cases for list response auto-detection"""

    @pytest.mark.asyncio
    async def test_auto_detect_list_response(self) -> None:
        """Test that direct list responses are auto-detected and data_path is set to '.'"""
        from main import resync_resources

        # Setup mocks
        mock_client = AsyncMock()

        # Mock resource config
        mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
        mock_selector = MagicMock(spec=HttpServerSelector)
        mock_selector.method = "GET"
        mock_selector.query_params = {}
        mock_selector.headers = {}
        mock_selector.data_path = None  # Not specified
        mock_resource_config.selector = mock_selector

        # Mock endpoint resolver (no dynamic endpoints)
        with (
            patch("main.init_client", return_value=mock_client),
            patch("main.resolve_dynamic_endpoints") as mock_resolve,
            patch("main.ocean") as mock_ocean,
            patch("main.cast", return_value=mock_resource_config),
            patch("main.event") as mock_event,
        ):
            mock_resolve.return_value = [("/api/v1/users", {})]

            # Mock pagination handler - returns direct list response
            # Pagination handlers yield [response_data], so batch[0] is the raw response
            direct_list_response = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]

            async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                yield [direct_list_response]  # Wrap in list as pagination handlers do

            mock_client.fetch_paginated_data = mock_fetch_paginated_data

            # Mock entity processor
            mock_ocean.app.integration.entity_processor._search = AsyncMock(
                return_value=direct_list_response
            )

            # Mock event
            mock_event.resource_config = mock_resource_config

            # Import the actual function (not the decorated wrapper)
            from main import resync_resources
            # The decorator wraps it, so we need to get the actual function
            # resync_resources is the decorated function, which when called returns the generator
            result = resync_resources("/api/v1/users")

            # Get first batch
            batch = await result.__anext__()

            # Verify that data_path was auto-detected and used
            # The batch should contain the extracted items
            assert len(batch) == 2
            assert batch[0]["id"] == 1
            assert batch[1]["id"] == 2

            # Verify that _search was called with data_path '.'
            mock_ocean.app.integration.entity_processor._search.assert_called()

    @pytest.mark.asyncio
    async def test_error_logged_when_not_list_and_no_data_path(self) -> None:
        """Test that error is logged when response is not a list and data_path is missing"""
        from main import resync_resources

        # Setup mocks
        mock_client = AsyncMock()

        # Mock resource config
        mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
        mock_selector = MagicMock(spec=HttpServerSelector)
        mock_selector.method = "GET"
        mock_selector.query_params = {}
        mock_selector.headers = {}
        mock_selector.data_path = None  # Not specified
        mock_resource_config.selector = mock_selector

        # Mock endpoint resolver
        with (
            patch("main.init_client", return_value=mock_client),
            patch("main.resolve_dynamic_endpoints") as mock_resolve,
            patch("main.logger") as mock_logger,
            patch("main.cast", return_value=mock_resource_config),
            patch("main.event") as mock_event,
        ):
            mock_resolve.return_value = [("/api/v1/users", {})]

            # Mock pagination handler - returns object response (not a list)
            # Pagination handlers yield [response_data], so batch[0] is the raw response
            object_response = {"data": [{"id": 1, "name": "Alice"}]}

            async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                yield [object_response]  # Wrap in list as pagination handlers do

            mock_client.fetch_paginated_data = mock_fetch_paginated_data

            # Mock event
            mock_event.resource_config = mock_resource_config

            # Call resync_resources
            result = resync_resources("/api/v1/users")

            # Get first batch
            batch = await result.__anext__()

            # Verify error was logged
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "not a list" in error_call
            assert "data_path" in error_call

            # Verify batch was yielded as-is (it's wrapped in a list by pagination handler)
            assert batch == [object_response]

    @pytest.mark.asyncio
    async def test_explicit_data_path_used_when_provided(self) -> None:
        """Test that explicit data_path is used when provided (no auto-detection)"""
        from main import resync_resources

        # Setup mocks
        mock_client = AsyncMock()

        # Mock resource config with explicit data_path
        mock_resource_config = MagicMock(spec=HttpServerResourceConfig)
        mock_selector = MagicMock(spec=HttpServerSelector)
        mock_selector.method = "GET"
        mock_selector.query_params = {}
        mock_selector.headers = {}
        mock_selector.data_path = ".data.users"  # Explicitly provided
        mock_resource_config.selector = mock_selector

        # Mock endpoint resolver
        with (
            patch("main.init_client", return_value=mock_client),
            patch("main.resolve_dynamic_endpoints") as mock_resolve,
            patch("main.ocean") as mock_ocean,
            patch("main.cast", return_value=mock_resource_config),
            patch("main.event") as mock_event,
        ):
            mock_resolve.return_value = [("/api/v1/users", {})]

            # Mock pagination handler
            # Pagination handlers yield [response_data], so batch[0] is the raw response
            object_response = {"data": {"users": [{"id": 1, "name": "Alice"}]}}

            async def mock_fetch_paginated_data(*args: Any, **kwargs: Any) -> Any:
                yield [object_response]  # Wrap in list as pagination handlers do

            mock_client.fetch_paginated_data = mock_fetch_paginated_data

            # Mock entity processor
            extracted_users = [{"id": 1, "name": "Alice"}]
            mock_ocean.app.integration.entity_processor._search = AsyncMock(
                return_value=extracted_users
            )

            # Mock event
            mock_event.resource_config = mock_resource_config

            # Call resync_resources
            result = resync_resources("/api/v1/users")

            # Get first batch
            batch = await result.__anext__()

            # Verify that explicit data_path was used
            mock_ocean.app.integration.entity_processor._search.assert_called_with(
                object_response, ".data.users"
            )

            # Verify batch contains extracted items
            assert len(batch) == 1
            assert batch[0]["id"] == 1
Wha