"""Tests for pagination handlers, particularly cursor pagination."""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from http_server.handlers import CursorPagination


class TestCursorPaginationHasMore:
    """Tests for cursor pagination has_more behavior."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock(spec=httpx.AsyncClient)

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Helper to get nested value from dict."""
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return None
        return data

    def _create_handler(
        self, responses: List[httpx.Response], config: Dict[str, Any]
    ) -> CursorPagination:
        """Helper to create a CursorPagination handler with mocked request function."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # Create a mock request function that returns responses in order
        response_iter = iter(responses)

        async def mock_make_request(
            url: str,
            method: str,
            params: Dict[str, Any],
            headers: Dict[str, str],
            body: Any = None,
        ) -> httpx.Response:
            return next(response_iter)

        return CursorPagination(
            client=mock_client,
            config=config,
            extract_items_fn=lambda x: x if isinstance(x, list) else [x],
            make_request_fn=mock_make_request,
            get_nested_value_fn=self._get_nested_value,
        )

    @pytest.mark.asyncio
    async def test_slack_style_pagination_empty_cursor_stops(self) -> None:
        """Test that pagination stops when cursor is empty (Slack-style API)."""
        # Slack returns empty string for next_cursor when no more pages
        responses = [
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "members": [{"id": "U1"}],
                    "response_metadata": {"next_cursor": "cursor_page2"},
                },
            ),
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "members": [{"id": "U2"}],
                    "response_metadata": {"next_cursor": ""},  # Empty = no more pages
                },
            ),
        ]

        handler = self._create_handler(
            responses,
            {
                "page_size": 100,
                "cursor_path": "response_metadata.next_cursor",
            },
        )

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.slack.com/users.list", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_slack_style_pagination_null_cursor_stops(self) -> None:
        """Test that pagination stops when cursor is null/None."""
        responses = [
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "items": [{"id": "1"}],
                    "response_metadata": {"next_cursor": "abc123"},
                },
            ),
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "items": [{"id": "2"}],
                    "response_metadata": {},  # No next_cursor key
                },
            ),
        ]

        handler = self._create_handler(
            responses,
            {
                "page_size": 100,
                "cursor_path": "response_metadata.next_cursor",
            },
        )

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/items", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_explicit_has_more_false_stops(self) -> None:
        """Test that explicit has_more=False stops pagination even with cursor."""
        responses = [
            httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "next_cursor": "page2",
                    "has_more": True,
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "2"}],
                    "next_cursor": "page3",  # Cursor exists but...
                    "has_more": False,  # ...has_more is explicitly False
                },
            ),
        ]

        handler = self._create_handler(responses, {"page_size": 100})

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/data", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_has_more_path_configured_uses_it(self) -> None:
        """Test that has_more_path is used when configured."""
        responses = [
            httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "next_cursor": "page2",
                    "pagination": {"continue": True},
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "2"}],
                    "next_cursor": "page3",
                    "pagination": {"continue": False},  # Should stop
                },
            ),
        ]

        handler = self._create_handler(
            responses,
            {
                "page_size": 100,
                "has_more_path": "pagination.continue",
            },
        )

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/data", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_no_has_more_field_continues_until_empty_cursor(self) -> None:
        """Test that without has_more field, pagination continues until cursor is empty."""
        responses = [
            httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "next_cursor": "page2",
                    # No has_more field at all
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "2"}],
                    "next_cursor": "page3",
                    # No has_more field at all
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "3"}],
                    "next_cursor": "",  # Empty cursor stops pagination
                },
            ),
        ]

        handler = self._create_handler(responses, {"page_size": 100})

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/data", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_hasMore_camelCase_field_works(self) -> None:
        """Test that hasMore (camelCase) field is recognized."""
        responses = [
            httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "next_cursor": "page2",
                    "hasMore": True,
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "2"}],
                    "next_cursor": "page3",
                    "hasMore": False,
                },
            ),
        ]

        handler = self._create_handler(responses, {"page_size": 100})

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/data", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_meta_has_more_field_works(self) -> None:
        """Test that meta.has_more field is recognized."""
        responses = [
            httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "next_cursor": "page2",
                    "meta": {"has_more": True},
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "2"}],
                    "next_cursor": "page3",
                    "meta": {"has_more": False},
                },
            ),
        ]

        handler = self._create_handler(responses, {"page_size": 100})

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/data", "GET", {}, {}
        ):
            results.extend(batch)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_backward_compatibility_requires_both_cursor_and_has_more(
        self,
    ) -> None:
        """Test backward compatibility: when has_more is explicitly False, stop even with cursor."""
        responses = [
            httpx.Response(
                200,
                json={
                    "items": [{"id": "1"}],
                    "cursor": "next_page",
                    "has_more": False,  # Explicitly False should stop
                },
            ),
        ]

        handler = self._create_handler(responses, {"page_size": 100})

        results: List[Any] = []
        async for batch in handler.fetch_all(
            "https://api.example.com/items", "GET", {}, {}
        ):
            results.extend(batch)

        # Should only have 1 result because has_more=False
        assert len(results) == 1
