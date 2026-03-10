"""Tests for pagination handlers"""

from typing import Any, Dict, List
from unittest.mock import MagicMock
import pytest

from http_server.handlers import (
    NextLinkPagination,
    get_pagination_handler,
    PAGINATION_HANDLERS,
)


class TestNextLinkPagination:
    """Test cases for NextLinkPagination handler"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_extract_items(self) -> MagicMock:
        return MagicMock(side_effect=lambda data: data if isinstance(data, list) else [data])

    @pytest.fixture
    def mock_get_nested_value(self) -> MagicMock:
        def _get_nested(data: Dict[str, Any], path: str) -> Any:
            keys = path.split(".")
            value = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value
        return MagicMock(side_effect=_get_nested)

    async def test_single_page_no_next_link(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test pagination stops when no @odata.nextLink is present"""
        response_data = {
            "value": [{"id": "1"}, {"id": "2"}],
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data

        async def mock_make_request(
            url: str,
            method: str,
            params: Dict[str, Any],
            headers: Dict[str, str],
            body: Dict[str, Any] | None = None,
        ) -> MagicMock:
            return mock_response

        handler = NextLinkPagination(
            client=mock_client,
            config={},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://graph.microsoft.com/v1.0/applications",
            method="GET",
            params={"$top": "100"},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == [response_data]

    async def test_multiple_pages_with_next_link(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test pagination follows @odata.nextLink through multiple pages"""
        page1 = {
            "value": [{"id": "1"}, {"id": "2"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/applications?$skiptoken=abc123",
        }
        page2 = {
            "value": [{"id": "3"}, {"id": "4"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/applications?$skiptoken=def456",
        }
        page3 = {
            "value": [{"id": "5"}],
        }

        responses = [page1, page2, page3]
        response_index = 0
        captured_urls: List[str] = []
        captured_params: List[Dict[str, Any]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Dict[str, Any],
            headers: Dict[str, str],
            body: Dict[str, Any] | None = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_urls.append(url)
            captured_params.append(params)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = NextLinkPagination(
            client=mock_client,
            config={},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://graph.microsoft.com/v1.0/applications",
            method="GET",
            params={"$top": "100"},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 3
        assert results[0] == [page1]
        assert results[1] == [page2]
        assert results[2] == [page3]

        assert captured_urls[0] == "https://graph.microsoft.com/v1.0/applications"
        assert captured_urls[1] == "https://graph.microsoft.com/v1.0/applications?$skiptoken=abc123"
        assert captured_urls[2] == "https://graph.microsoft.com/v1.0/applications?$skiptoken=def456"

        assert captured_params[0] == {"$top": "100"}
        assert captured_params[1] == {}
        assert captured_params[2] == {}

    async def test_custom_next_link_path(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test pagination with custom next_link_path configuration"""
        page1 = {
            "data": [{"id": "1"}],
            "links": {"next": "https://api.example.com/items?page=2"},
        }
        page2 = {
            "data": [{"id": "2"}],
        }

        responses = [page1, page2]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Dict[str, Any],
            headers: Dict[str, str],
            body: Dict[str, Any] | None = None,
        ) -> MagicMock:
            nonlocal response_index
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        def custom_get_nested(data: Dict[str, Any], path: str) -> Any:
            if path == "links.next":
                return data.get("links", {}).get("next")
            return None

        handler = NextLinkPagination(
            client=mock_client,
            config={"next_link_path": "links.next"},
            extract_items_fn=mock_extract_items,
            make_request_fn=MagicMock(side_effect=mock_make_request),
            get_nested_value_fn=MagicMock(side_effect=custom_get_nested),
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 2


class TestPaginationHandlerRegistry:
    """Test cases for pagination handler registry"""

    def test_next_link_in_registry(self) -> None:
        """Test that next_link pagination type is registered"""
        assert "next_link" in PAGINATION_HANDLERS
        assert PAGINATION_HANDLERS["next_link"] == NextLinkPagination

    def test_get_pagination_handler_next_link(self) -> None:
        """Test get_pagination_handler returns NextLinkPagination for next_link type"""
        mock_client = MagicMock()
        handler = get_pagination_handler(
            pagination_type="next_link",
            client=mock_client,
            config={},
            extract_items_fn=MagicMock(),
            make_request_fn=MagicMock(),
            get_nested_value_fn=MagicMock(),
        )
        assert isinstance(handler, NextLinkPagination)

    def test_get_pagination_handler_invalid_type_defaults_to_none(self) -> None:
        """Test that invalid pagination type defaults to NonePagination"""
        from http_server.handlers import NonePagination

        mock_client = MagicMock()
        handler = get_pagination_handler(
            pagination_type="invalid_type",
            client=mock_client,
            config={},
            extract_items_fn=MagicMock(),
            make_request_fn=MagicMock(),
            get_nested_value_fn=MagicMock(),
        )
        assert isinstance(handler, NonePagination)
