"""
Handlers for HTTP Server integration.

Provides authentication and pagination handlers using strategy pattern.
"""

import httpx

from typing import Dict, Any, List, Callable, Awaitable
from collections.abc import AsyncGenerator as AsyncGenType


# ============================================================================
# Authentication Handlers
# ============================================================================


class AuthHandler:
    """Base class for authentication handlers"""

    def __init__(self, client: httpx.AsyncClient, config: Dict[str, Any]):
        self.client = client
        self.config = config

    def setup(self) -> None:
        """Setup authentication - override in subclasses"""
        pass


class BearerTokenAuth(AuthHandler):
    """Bearer token authentication"""

    def setup(self) -> None:
        token = self.config.get("api_token")
        if token:
            self.client.headers["Authorization"] = f"Bearer {token}"


class ApiKeyAuth(AuthHandler):
    """API key authentication"""

    def setup(self) -> None:
        api_key = self.config.get("api_key")
        key_header = self.config.get("api_key_header", "X-API-Key")
        if api_key and key_header:
            self.client.headers[key_header] = api_key


class BasicAuth(AuthHandler):
    """Basic authentication"""

    def setup(self) -> None:
        username = self.config.get("username")
        password = self.config.get("password")
        if username and password:
            self.client.auth = httpx.BasicAuth(username, password)


class NoAuth(AuthHandler):
    """No authentication"""

    def setup(self) -> None:
        pass


# Registry of available auth handlers
AUTH_HANDLERS = {
    "bearer_token": BearerTokenAuth,
    "api_key": ApiKeyAuth,
    "basic": BasicAuth,
    "none": NoAuth,
}


def get_auth_handler(
    auth_type: str, client: httpx.AsyncClient, config: Dict[str, Any]
) -> AuthHandler:
    """Get the appropriate authentication handler"""
    handler_class = AUTH_HANDLERS.get(auth_type, NoAuth)
    return handler_class(client, config)


# ============================================================================
# Pagination Handlers
# ============================================================================


class PaginationHandler:
    """Base class for pagination handlers"""

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: Dict[str, Any],
        extract_items_fn: Callable[[Any], List[Dict[str, Any]]],
        make_request_fn: Callable[
            [str, str, Dict[str, Any], Dict[str, str]], Awaitable[httpx.Response]
        ],
        get_nested_value_fn: Callable[[Dict[str, Any], str], Any],
    ) -> None:
        self.client = client
        self.config = config
        self.extract_items = extract_items_fn
        self.make_request = make_request_fn
        self.get_nested_value = get_nested_value_fn
        self.page_size = int(config.get("page_size", 100))

    async def fetch_all(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenType[List[Dict[str, Any]], None]:
        """Fetch all pages - override in subclasses"""
        raise NotImplementedError
        yield  # Make this actually a generator for type checking


class NonePagination(PaginationHandler):
    """No pagination - single request"""

    async def fetch_all(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenType[List[Dict[str, Any]], None]:
        response = await self.make_request(url, method, params, headers)
        response_data = response.json()
        # Yield raw response as single-item batch for Ocean's data_path extraction
        yield [response_data]


class PagePagination(PaginationHandler):
    """Page/size pagination with configurable response paths"""

    async def fetch_all(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenType[List[Dict[str, Any]], None]:
        page_param = self.config.get("pagination_param", "page")
        size_param = self.config.get("size_param", "size")
        start_page = int(self.config.get("start_page", 1))
        has_more_path = self.config.get("has_more_path", "")

        page = start_page

        while True:
            current_params = {
                **params,
                page_param: page,
                size_param: self.page_size,
            }

            response = await self.make_request(url, method, current_params, headers)
            response_data = response.json()

            # Yield raw response as single-item batch
            yield [response_data]

            # Check for next page
            if isinstance(response_data, dict):
                if has_more_path:
                    has_next = self.get_nested_value(response_data, has_more_path)
                else:
                    has_next = (
                        response_data.get("next_page") is not None
                        or response_data.get("next") is not None
                        or response_data.get("hasMore", False)
                    )
                if not has_next:
                    break
            else:
                # For list responses, check if we got a full page
                if (
                    isinstance(response_data, list)
                    and len(response_data) < self.page_size
                ):
                    break

            page += 1


class OffsetPagination(PaginationHandler):
    """Offset/limit pagination with configurable response paths"""

    async def fetch_all(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenType[List[Dict[str, Any]], None]:
        offset_param = self.config.get("pagination_param", "offset")
        limit_param = self.config.get("size_param", "limit")
        has_more_path = self.config.get("has_more_path", "")

        offset = 0

        while True:
            current_params = {
                **params,
                offset_param: offset,
                limit_param: self.page_size,
            }

            response = await self.make_request(url, method, current_params, headers)
            response_data = response.json()

            # Yield raw response as single-item batch
            yield [response_data]

            # Check if there are more pages
            if isinstance(response_data, dict):
                if has_more_path:
                    has_more = self.get_nested_value(response_data, has_more_path)
                else:
                    has_more = response_data.get(
                        "has_more", response_data.get("hasMore", True)
                    )
                if not has_more:
                    break
            else:
                # For list responses, check if we got a full page
                if (
                    isinstance(response_data, list)
                    and len(response_data) < self.page_size
                ):
                    break

            offset += self.page_size


class CursorPagination(PaginationHandler):
    """Cursor-based pagination with configurable response paths"""

    async def fetch_all(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenType[List[Dict[str, Any]], None]:
        cursor_param = self.config.get("pagination_param", "cursor")
        limit_param = self.config.get("size_param", "limit")
        cursor_path = self.config.get("cursor_path", "")
        has_more_path = self.config.get("has_more_path", "")

        cursor = None

        while True:
            current_params = {**params, limit_param: self.page_size}

            if cursor:
                current_params[cursor_param] = cursor

            response = await self.make_request(url, method, current_params, headers)
            response_data = response.json()

            # Yield raw response as single-item batch
            yield [response_data]

            # For dict responses, extract cursor and check has_more
            if isinstance(response_data, dict):
                # Extract cursor
                next_cursor = None
                if cursor_path:
                    next_cursor = self.get_nested_value(response_data, cursor_path)
                else:
                    next_cursor = (
                        response_data.get("next_cursor")
                        or response_data.get("cursor")
                        or response_data.get("meta", {}).get("after_cursor")
                        or response_data.get("links", {}).get("next")
                    )

                # Check has_more
                has_more = False
                if has_more_path:
                    has_more = self.get_nested_value(response_data, has_more_path)
                else:
                    has_more = response_data.get(
                        "has_more",
                        response_data.get(
                            "hasMore",
                            response_data.get("meta", {}).get("has_more", False),
                        ),
                    )

                # Stop if no more pages
                if not next_cursor or not has_more:
                    break

                # Update cursor for next iteration
                cursor = next_cursor
            else:
                # List response - no more pagination
                break


# Registry of available pagination handlers
PAGINATION_HANDLERS = {
    "none": NonePagination,
    "page": PagePagination,
    "offset": OffsetPagination,
    "cursor": CursorPagination,
}


def get_pagination_handler(
    pagination_type: str,
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    extract_items_fn: Callable[[Any], List[Dict[str, Any]]],
    make_request_fn: Callable[
        [str, str, Dict[str, Any], Dict[str, str]], Awaitable[httpx.Response]
    ],
    get_nested_value_fn: Callable[[Dict[str, Any], str], Any],
) -> PaginationHandler:
    """Get the appropriate pagination handler"""
    handler_class = PAGINATION_HANDLERS.get(pagination_type, NonePagination)
    return handler_class(
        client, config, extract_items_fn, make_request_fn, get_nested_value_fn
    )
