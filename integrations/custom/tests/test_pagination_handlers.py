"""Tests for pagination handlers"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
import pytest

from http_server.handlers import (
    NextLinkPagination,
    HeaderLinkPagination,
    PagePagination,
    CursorPagination,
    OffsetPagination,
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
        return MagicMock(
            side_effect=lambda data: data if isinstance(data, list) else [data]
        )

    @pytest.fixture
    def mock_get_nested_value(self) -> MagicMock:
        def _get_nested(data: Dict[str, Any], path: str) -> Any:
            keys = path.split(".")
            value: Any = data
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
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
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
        captured_params: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
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
        assert (
            captured_urls[1]
            == "https://graph.microsoft.com/v1.0/applications?$skiptoken=abc123"
        )
        assert (
            captured_urls[2]
            == "https://graph.microsoft.com/v1.0/applications?$skiptoken=def456"
        )

        assert captured_params[0] == {"$top": "100"}
        assert captured_params[1] is None
        assert captured_params[2] is None

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
        captured_urls: List[str] = []
        captured_params: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_urls.append(url)
            captured_params.append(params)
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
            params={"initial": "param"},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 2
        assert results[0] == [page1]
        assert results[1] == [page2]

        assert captured_urls[0] == "https://api.example.com/items"
        assert captured_urls[1] == "https://api.example.com/items?page=2"

        assert captured_params[0] == {"initial": "param"}
        assert captured_params[1] is None

    async def test_relative_next_link_resolved_against_base_url(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Relative next links are resolved against integration base_url"""
        page1 = {
            "results": [{"id": "1"}],
            "_links": {"next": "/wiki/api/v2/spaces?cursor=page2"},
        }
        page2 = {"results": [{"id": "2"}]}

        responses = [page1, page2]
        response_index = 0
        captured_urls: List[str] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_urls.append(url)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = NextLinkPagination(
            client=mock_client,
            config={
                "next_link_path": "_links.next",
                "base_url": "https://api.example.com/ex/tenant/cloud-id-123",
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/ex/tenant/cloud-id-123/wiki/api/v2/spaces",
            method="GET",
            params={},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 2
        assert (
            captured_urls[1]
            == "https://api.example.com/ex/tenant/cloud-id-123/wiki/api/v2/spaces?cursor=page2"
        )


class TestCursorPagination:
    """Test cases for CursorPagination handler"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_extract_items(self) -> MagicMock:
        return MagicMock(
            side_effect=lambda data: data if isinstance(data, list) else [data]
        )

    @pytest.fixture
    def mock_get_nested_value(self) -> MagicMock:
        def _get_nested(data: Dict[str, Any], path: str) -> Any:
            current: Any = data
            for key in path.split("."):
                if not isinstance(current, dict) or key not in current:
                    return None
                current = current[key]
            return current

        return MagicMock(side_effect=_get_nested)

    async def test_body_placement_omits_cursor_on_first_page(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Body placement sends size in body and omits cursor on page 1"""
        page1 = {
            "data": [{"id": "1"}],
            "next_page_token": "tok-2",
            "has_more": True,
        }
        page2 = {"data": [{"id": "2"}], "has_more": False}

        responses = [page1, page2]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = CursorPagination(
            client=mock_client,
            config={
                "pagination_placement": "body",
                "pagination_param": "next_page_token",
                "size_param": "limit",
                "cursor_path": "next_page_token",
                "has_more_path": "has_more",
                "page_size": 100,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/query",
            method="POST",
            params={},
            headers={},
            body={"query": "status = open"},
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_bodies[0] == {
            "query": "status = open",
            "limit": 100,
        }
        assert "next_page_token" not in (captured_bodies[0] or {})
        assert captured_bodies[1] == {
            "query": "status = open",
            "limit": 100,
            "next_page_token": "tok-2",
        }
        assert "next_page_token" not in (captured_params[0] or {})
        assert "next_page_token" not in (captured_params[1] or {})

    async def test_query_placement_keeps_cursor_in_params(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Default query placement puts cursor in query params and leaves body alone"""
        page1 = {
            "data": [{"id": "1"}],
            "next_cursor": "c2",
            "has_more": True,
        }
        page2 = {"data": [{"id": "2"}], "has_more": False}

        responses = [page1, page2]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = CursorPagination(
            client=mock_client,
            config={
                "pagination_param": "cursor",
                "size_param": "limit",
                "cursor_path": "next_cursor",
                "has_more_path": "has_more",
                "page_size": 50,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        original_body = {"filter": "active"}
        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
            body=original_body,
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_params[0] == {"limit": 50}
        assert captured_params[1] == {"limit": 50, "cursor": "c2"}
        assert captured_bodies[0] is original_body
        assert captured_bodies[1] is original_body

    async def test_get_with_body_placement_falls_back_to_query(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """GET ignores body placement and puts cursor/limit in query params"""
        page1 = {
            "data": [{"id": "1"}],
            "next_cursor": "c2",
            "has_more": True,
        }
        page2 = {"data": [{"id": "2"}], "has_more": False}

        responses = [page1, page2]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = CursorPagination(
            client=mock_client,
            config={
                "pagination_placement": "body",
                "pagination_param": "cursor",
                "size_param": "limit",
                "cursor_path": "next_cursor",
                "has_more_path": "has_more",
                "page_size": 25,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        original_body = {"filter": "active"}
        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
            body=original_body,
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_params[0] == {"limit": 25}
        assert captured_params[1] == {"limit": 25, "cursor": "c2"}
        assert captured_bodies[0] is original_body
        assert captured_bodies[1] is original_body
        assert "cursor" not in (captured_bodies[0] or {})
        assert "limit" not in (captured_bodies[0] or {})

    async def test_repeated_cursor_stops_pagination(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Identical next cursor with has_more true still terminates the loop"""
        stuck_page = {
            "data": [{"id": "1"}],
            "next_cursor": "same-token",
            "has_more": True,
        }

        request_count = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal request_count
            request_count += 1
            if request_count > 3:
                raise AssertionError("pagination did not stop on repeated cursor")
            mock_response = MagicMock()
            mock_response.json.return_value = stuck_page
            return mock_response

        handler = CursorPagination(
            client=mock_client,
            config={
                "pagination_param": "cursor",
                "size_param": "limit",
                "cursor_path": "next_cursor",
                "has_more_path": "has_more",
                "page_size": 10,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
        ):
            results.append(batch)

        # Page 1 has no prior cursor; page 2 repeats "same-token" and must stop.
        assert len(results) == 2
        assert request_count == 2


class TestOffsetPagination:
    """Test cases for OffsetPagination handler"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_extract_items(self) -> MagicMock:
        return MagicMock(
            side_effect=lambda data: data if isinstance(data, list) else [data]
        )

    @pytest.fixture
    def mock_get_nested_value(self) -> MagicMock:
        def _get_nested(data: Dict[str, Any], path: str) -> Any:
            current: Any = data
            for key in path.split("."):
                if not isinstance(current, dict) or key not in current:
                    return None
                current = current[key]
            return current

        return MagicMock(side_effect=_get_nested)

    async def test_body_placement_sends_offset_and_limit_in_body(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Body placement merges offset + limit into the POST body on every page"""
        page1 = {
            "status": "success",
            "data": [{"id": "1"}] * 100,
            "total_items": 200,
        }
        page2 = {
            "status": "success",
            "data": [{"id": "2"}] * 100,
            "total_items": 200,
        }

        responses = [page1, page2]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = OffsetPagination(
            client=mock_client,
            config={
                "pagination_placement": "body",
                "pagination_param": "start_at_index",
                "size_param": "limit",
                "total_count_path": "total_items",
                "page_size": 100,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/serving-layer/query",
            method="POST",
            params={},
            headers={},
            body={"query": {"models": ["Alert"]}, "get_results_and_count": True},
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_bodies[0] == {
            "query": {"models": ["Alert"]},
            "get_results_and_count": True,
            "start_at_index": 0,
            "limit": 100,
        }
        assert captured_bodies[1] == {
            "query": {"models": ["Alert"]},
            "get_results_and_count": True,
            "start_at_index": 100,
            "limit": 100,
        }
        assert "start_at_index" not in (captured_params[0] or {})
        assert "limit" not in (captured_params[0] or {})

    async def test_query_placement_keeps_offset_in_params(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Default query placement puts offset/limit in query params and leaves body alone"""
        page1 = {"data": [{"id": "1"}] * 50, "has_more": True}
        page2 = {"data": [{"id": "2"}], "has_more": False}

        responses = [page1, page2]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = OffsetPagination(
            client=mock_client,
            config={
                "pagination_param": "offset",
                "size_param": "limit",
                "page_size": 50,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        original_body = {"filter": "active"}
        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
            body=original_body,
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_params[0] == {"offset": 0, "limit": 50}
        assert captured_params[1] == {"offset": 50, "limit": 50}
        assert captured_bodies[0] is original_body
        assert captured_bodies[1] is original_body

    async def test_get_with_body_placement_falls_back_to_query(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """GET ignores body placement and puts offset/limit in query params"""
        page1 = {"data": [{"id": "1"}] * 25, "has_more": True}
        page2 = {"data": [{"id": "2"}], "has_more": False}

        responses = [page1, page2]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = OffsetPagination(
            client=mock_client,
            config={
                "pagination_placement": "body",
                "pagination_param": "offset",
                "size_param": "limit",
                "page_size": 25,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        original_body = {"filter": "active"}
        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
            body=original_body,
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_params[0] == {"offset": 0, "limit": 25}
        assert captured_params[1] == {"offset": 25, "limit": 25}
        assert captured_bodies[0] is original_body
        assert captured_bodies[1] is original_body
        assert "offset" not in (captured_bodies[0] or {})
        assert "limit" not in (captured_bodies[0] or {})

    async def test_initial_offset_and_total_count_path(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """initial_offset starts paging at 1 and total_count_path stops past total_items"""
        page1 = {
            "status": "success",
            "data": [{"id": "1"}] * 100,
            "total_items": 200,
        }
        page2 = {
            "status": "success",
            "data": [{"id": "2"}] * 100,
            "total_items": 200,
        }

        responses = [page1, page2]
        response_index = 0
        captured_bodies: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_bodies.append(body)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = OffsetPagination(
            client=mock_client,
            config={
                "pagination_placement": "body",
                "pagination_param": "start_at_index",
                "size_param": "limit",
                "initial_offset": 1,
                "total_count_path": "total_items",
                "page_size": 100,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/query",
            method="POST",
            params={},
            headers={},
            body={"query": "open alerts"},
        ):
            results.append(batch)

        assert len(results) == 2
        assert captured_bodies[0] is not None
        assert captured_bodies[1] is not None
        assert captured_bodies[0]["start_at_index"] == 1
        assert captured_bodies[1]["start_at_index"] == 101

    async def test_stops_without_has_more_when_data_is_short(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Dict responses without has_more stop on a short data page (no infinite loop)"""
        stuck_page = {"status": "success", "data": [{"id": "1"}]}

        request_count = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal request_count
            request_count += 1
            if request_count > 3:
                raise AssertionError("pagination did not stop without has_more")
            mock_response = MagicMock()
            mock_response.json.return_value = stuck_page
            return mock_response

        handler = OffsetPagination(
            client=mock_client,
            config={
                "pagination_param": "offset",
                "size_param": "limit",
                "page_size": 100,
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 1
        assert request_count == 1


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

    def test_page_in_registry(self) -> None:
        """Test that page pagination type is registered"""
        assert "page" in PAGINATION_HANDLERS
        assert PAGINATION_HANDLERS["page"] == PagePagination

    def test_get_pagination_handler_page(self) -> None:
        """Test get_pagination_handler returns PagePagination for page type"""
        mock_client = MagicMock()
        handler = get_pagination_handler(
            pagination_type="page",
            client=mock_client,
            config={},
            extract_items_fn=MagicMock(),
            make_request_fn=MagicMock(),
            get_nested_value_fn=MagicMock(),
        )
        assert isinstance(handler, PagePagination)

    def test_header_link_in_registry(self) -> None:
        """Test that header_link pagination type is registered"""
        assert "header_link" in PAGINATION_HANDLERS
        assert PAGINATION_HANDLERS["header_link"] == HeaderLinkPagination

    def test_get_pagination_handler_header_link(self) -> None:
        """Test get_pagination_handler returns HeaderLinkPagination for header_link type"""
        mock_client = MagicMock()
        handler = get_pagination_handler(
            pagination_type="header_link",
            client=mock_client,
            config={},
            extract_items_fn=MagicMock(),
            make_request_fn=MagicMock(),
            get_nested_value_fn=MagicMock(),
        )
        assert isinstance(handler, HeaderLinkPagination)


class TestHeaderLinkPagination:
    """Test cases for HeaderLinkPagination handler"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_extract_items(self) -> MagicMock:
        return MagicMock(
            side_effect=lambda data: data if isinstance(data, list) else [data]
        )

    @pytest.fixture
    def mock_get_nested_value(self) -> MagicMock:
        return MagicMock()

    async def test_single_page_no_link_header(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test pagination stops when no Link header is present"""
        response_data = [{"id": "1"}, {"id": "2"}]

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.links = {}

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            return mock_response

        handler = HeaderLinkPagination(
            client=mock_client,
            config={},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.github.com/users/octocat/repos",
            method="GET",
            params={"per_page": "100"},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == [response_data]

    async def test_multiple_pages_with_link_header(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test pagination follows Link header through multiple pages"""
        page1 = [{"id": "1"}, {"id": "2"}]
        page2 = [{"id": "3"}, {"id": "4"}]
        page3 = [{"id": "5"}]

        responses = [
            (page1, {"next": {"url": "https://api.github.com/repos?page=2"}}),
            (page2, {"next": {"url": "https://api.github.com/repos?page=3"}}),
            (page3, {}),
        ]
        response_index = 0
        captured_urls: List[str] = []
        captured_params: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_urls.append(url)
            captured_params.append(params)
            data, links = responses[response_index]
            mock_response = MagicMock()
            mock_response.json.return_value = data
            mock_response.links = links
            response_index += 1
            return mock_response

        handler = HeaderLinkPagination(
            client=mock_client,
            config={},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.github.com/users/octocat/repos",
            method="GET",
            params={"per_page": "100"},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 3
        assert results[0] == [page1]
        assert results[1] == [page2]
        assert results[2] == [page3]

        assert captured_urls[0] == "https://api.github.com/users/octocat/repos"
        assert captured_params[0] == {"per_page": "100"}

        assert captured_urls[1] == "https://api.github.com/repos?page=2"
        assert captured_params[1] is None

        assert captured_urls[2] == "https://api.github.com/repos?page=3"
        assert captured_params[2] is None

    async def test_custom_rel_value(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test pagination with custom rel value from config"""
        page1 = [{"id": "1"}]
        page2 = [{"id": "2"}]

        responses = [
            (page1, {"nextPage": {"url": "https://api.example.com/items?page=2"}}),
            (page2, {}),
        ]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            data, links = responses[response_index]
            mock_response = MagicMock()
            mock_response.json.return_value = data
            mock_response.links = links
            response_index += 1
            return mock_response

        handler = HeaderLinkPagination(
            client=mock_client,
            config={"header_link_rel": "nextPage"},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
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


class TestPagePagination:
    """Test cases for PagePagination handler"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_extract_items(self) -> MagicMock:
        return MagicMock(
            side_effect=lambda data: data if isinstance(data, list) else [data]
        )

    @pytest.fixture
    def mock_get_nested_value(self) -> MagicMock:
        def _get_nested(data: Dict[str, Any], path: str) -> Any:
            keys = path.split(".")
            value: Any = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value

        return MagicMock(side_effect=_get_nested)

    async def test_spring_envelope_multi_page(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test Spring Data REST style with data.last: false/false/true"""
        page1 = {
            "status": "SUCCESS",
            "data": {
                "content": [{"id": "1"}, {"id": "2"}],
                "totalPages": 3,
                "last": False,
                "number": 0,
                "size": 10,
            },
        }
        page2 = {
            "status": "SUCCESS",
            "data": {
                "content": [{"id": "3"}, {"id": "4"}],
                "totalPages": 3,
                "last": False,
                "number": 1,
                "size": 10,
            },
        }
        page3 = {
            "status": "SUCCESS",
            "data": {
                "content": [{"id": "5"}],
                "totalPages": 3,
                "last": True,
                "number": 2,
                "size": 10,
            },
        }

        responses = [page1, page2, page3]
        response_index = 0
        captured_params: List[Optional[Dict[str, Any]]] = []

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            captured_params.append(params)
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = PagePagination(
            client=mock_client,
            config={
                "pagination_param": "page",
                "size_param": "size",
                "start_page": "0",
                "page_size": "10",
                "last_page_path": "data.last",
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
        ):
            results.append(batch)

        assert len(results) == 3
        assert results[0] == [page1]
        assert results[1] == [page2]
        assert results[2] == [page3]

        assert captured_params[0] == {"page": 0, "size": 10}
        assert captured_params[1] == {"page": 1, "size": 10}
        assert captured_params[2] == {"page": 2, "size": 10}

    async def test_default_heuristic(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test default heuristic with hasMore: true then false"""
        page1 = {"items": [{"id": "1"}], "hasMore": True}
        page2 = {"items": [{"id": "2"}], "hasMore": False}

        responses = [page1, page2]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = PagePagination(
            client=mock_client,
            config={"page_size": "10"},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
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

    async def test_has_more_path_regression(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test has_more_path still works (regression)"""
        page1 = {"data": {"has_more": True, "items": [{"id": "1"}]}}
        page2 = {"data": {"has_more": False, "items": [{"id": "2"}]}}

        responses = [page1, page2]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = PagePagination(
            client=mock_client,
            config={"page_size": "10", "has_more_path": "data.has_more"},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
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

    async def test_has_more_path_takes_precedence(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test has_more_path wins when both has_more_path and last_page_path are set"""
        page1 = {"data": {"has_more": True, "last": True}, "items": [{"id": "1"}]}
        page2 = {"data": {"has_more": False, "last": False}, "items": [{"id": "2"}]}

        responses = [page1, page2]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = PagePagination(
            client=mock_client,
            config={
                "page_size": "10",
                "has_more_path": "data.has_more",
                "last_page_path": "data.last",
            },
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
        )

        results: List[List[Dict[str, Any]]] = []
        async for batch in handler.fetch_all(
            url="https://api.example.com/items",
            method="GET",
            params={},
            headers={},
        ):
            results.append(batch)

        # has_more_path wins: page1 has_more=True -> continue, page2 has_more=False -> stop
        assert len(results) == 2

    async def test_missing_last_field_falls_through(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test that missing last_page_path field falls through to defaults"""
        page1 = {"data": {"items": [{"id": "1"}]}, "hasMore": True}
        page2 = {"data": {"items": [{"id": "2"}]}, "hasMore": False}

        responses = [page1, page2]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = PagePagination(
            client=mock_client,
            config={"page_size": "10", "last_page_path": "data.last"},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
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

    async def test_has_more_path_missing_field_falls_through(
        self,
        mock_client: MagicMock,
        mock_extract_items: MagicMock,
        mock_get_nested_value: MagicMock,
    ) -> None:
        """Test that missing has_more_path field falls through to defaults"""
        page1 = {"items": [{"id": "1"}], "hasMore": True}
        page2 = {"items": [{"id": "2"}], "hasMore": False}

        responses = [page1, page2]
        response_index = 0

        async def mock_make_request(
            url: str,
            method: str,
            params: Optional[Dict[str, Any]],
            headers: Dict[str, str],
            body: Optional[Dict[str, Any]] = None,
        ) -> MagicMock:
            nonlocal response_index
            mock_response = MagicMock()
            mock_response.json.return_value = responses[response_index]
            response_index += 1
            return mock_response

        handler = PagePagination(
            client=mock_client,
            config={"page_size": "10", "has_more_path": "data.has_more"},
            extract_items_fn=mock_extract_items,
            make_request_fn=mock_make_request,
            get_nested_value_fn=mock_get_nested_value,
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
