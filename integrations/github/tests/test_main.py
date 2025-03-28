import pytest
from unittest.mock import MagicMock, patch
from helpers.utils import ObjectKind


# Mock the Ocean decorators before importing main
def mock_decorator(*args, **kwargs):
    def wrapper(func):
        return func

    if len(args) == 1 and callable(args[0]):
        return wrapper(args[0])
    return wrapper


# Patch the Ocean decorators
with (
    patch("port_ocean.context.ocean.ocean.on_resync", mock_decorator),
    patch("port_ocean.context.ocean.ocean.on_start", mock_decorator),
    patch("port_ocean.context.ocean.ocean.add_webhook_processor", mock_decorator),
):
    from main import on_global_resync


@pytest.mark.asyncio
class TestGlobalResync:
    async def test_skips_known_kinds(self):
        """Test that known kinds are skipped."""

        results = []
        async for items in on_global_resync(ObjectKind.REPOSITORY):
            results.extend(items)

        assert results == []  # Should be empty since known kinds are skipped

    async def test_unknown_kind_uses_pagination(self, mock_http_response):
        """Test that unknown kinds use direct pagination."""

        unknown_kind = "custom_resources"
        mock_items = [{"id": 1, "name": "custom1"}, {"id": 2, "name": "custom2"}]
        mock_http_response.json.side_effect = [
            mock_items,  # First page
            [],
        ]

        with patch(
            "port_ocean.utils.http_async_client.request",
            return_value=mock_http_response,
        ):

            results = []
            async for items in on_global_resync(unknown_kind):
                results.extend(items)

            assert results == mock_items

    async def test_pagination_with_multiple_pages(self):
        """Test pagination handling multiple pages."""

        unknown_kind = "custom_resources"
        page1_items = [{"id": 1, "name": "custom1"}]
        page2_items = [{"id": 2, "name": "custom2"}]

        mock_response = MagicMock()
        mock_response.json.side_effect = [
            page1_items,  # Page 1
            page2_items,  # Page 2
            [],
        ]

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            results = []
            async for items in on_global_resync(unknown_kind):
                results.extend(items)

            expected_items = page1_items + page2_items
            assert results == expected_items
