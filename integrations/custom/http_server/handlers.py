"""
Handlers for HTTP Server integration.

Provides authentication and pagination handlers using strategy pattern.
"""

import asyncio
import httpx
import re

from typing import Dict, Any, List, Callable, Awaitable, Optional
from collections.abc import AsyncGenerator as AsyncGenType

from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from loguru import logger
from port_ocean.context.ocean import ocean


# ============================================================================
# Template Evaluation Utilities
# ============================================================================


async def _evaluate_template(template: str, auth_response: Dict[str, Any]) -> str:
    """Evaluate template string by replacing {{.jq_path}} with values from auth_response.

    Example:
        template = "Bearer {{.access_token}}"
        auth_response = {"access_token": "abc123", "expires_in": 3600}
        Returns: "Bearer abc123"
    """
    if not auth_response:
        return template

    # Find all {{...}} patterns
    pattern = r"\{\{\.([^}]+)\}\}"
    matches = list(re.finditer(pattern, template))

    if not matches:
        return template

    # Extract all JQ paths and evaluate them concurrently
    jq_paths = [match.group(1) for match in matches]

    async def extract_value(jq_path: str) -> str:
        try:
            # Prepend dot to JQ path if not already present (JQ requires .field for object access)
            jq_expression = jq_path if jq_path.startswith(".") else f".{jq_path}"
            # Use Ocean's JQ processor to extract value (async)
            value = await ocean.app.integration.entity_processor._search(  # type: ignore[attr-defined]
                auth_response, jq_expression
            )
            if value is None:
                logger.warning(
                    f"CustomAuth: Template variable '{{.{jq_path}}}' not found in auth response"
                )
                return f"{{{{.{jq_path}}}}}"  # Return original template if not found
            return str(value)
        except Exception as e:
            logger.error(
                f"CustomAuth: Error evaluating template '{{.{jq_path}}}': {str(e)}"
            )
            return f"{{{{.{jq_path}}}}}"  # Return original template on error

    # Evaluate all JQ paths concurrently
    replacements = await asyncio.gather(*[extract_value(path) for path in jq_paths])

    # Replace matches in reverse order to preserve indices
    result = template
    for match, replacement in zip(reversed(matches), reversed(replacements)):
        result = result[: match.start()] + replacement + result[match.end() :]

    return result


async def _evaluate_templates_in_dict(
    data: Dict[str, Any], auth_response: Dict[str, Any]
) -> Dict[str, Any]:
    """Recursively evaluate templates in a dictionary (headers, queryParams, etc.)"""
    if not auth_response:
        return data

    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = await _evaluate_template(value, auth_response)
        elif isinstance(value, dict):
            result[key] = await _evaluate_templates_in_dict(value, auth_response)
        elif isinstance(value, list):
            evaluated_items = []
            for item in value:
                if isinstance(item, str):
                    evaluated_items.append(
                        await _evaluate_template(item, auth_response)
                    )
                else:
                    evaluated_items.append(item)
            result[key] = evaluated_items
        else:
            result[key] = value
    return result


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


class CustomAuth(AuthHandler):
    """Custom authentication with dynamic token retrieval"""

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: Dict[str, Any],
        custom_auth_request: Optional[CustomAuthRequestConfig],
        custom_auth_response: Optional[CustomAuthResponseConfig],
    ):
        super().__init__(client, config)
        self.custom_auth_request = custom_auth_request
        self.custom_auth_response = custom_auth_response
        self.token: Optional[str] = None
        self._lock = asyncio.Lock()  # Prevent concurrent re-auth
        self.base_url: str = config.get("base_url", "")
        self.auth_response: Optional[Dict[str, Any]] = None
        self.verify_ssl: bool = config.get("verify_ssl", True)

    def setup(self) -> None:
        """Setup authentication - performs blocking authentication"""
        if not self.custom_auth_request:
            logger.debug(
                "CustomAuth: No custom_auth_request configured, skipping setup"
            )
            return
        logger.info("CustomAuth: Starting initial authentication during setup")
        try:
            self.authenticate()
            logger.info("CustomAuth: Initial authentication completed successfully")
        except Exception as e:
            logger.error(f"CustomAuth: Failed to authenticate during setup: {str(e)}")
            raise

    def authenticate(self) -> None:
        """Make authentication request synchronously and store token (blocking)"""
        if not self.custom_auth_request:
            raise ValueError("customAuthRequest configuration is required")

        # Build the auth URL
        endpoint = self.custom_auth_request.endpoint
        if endpoint.startswith(("http://", "https://")):
            # Full URL provided
            auth_url = endpoint
            logger.debug(f"CustomAuth: Using full URL for authentication: {auth_url}")
        else:
            # Relative path - use base_url
            base_url = self.base_url.rstrip("/")
            endpoint_path = endpoint.lstrip("/")
            auth_url = f"{base_url}/{endpoint_path}"
            logger.debug(
                f"CustomAuth: Built auth URL from base_url and endpoint: {auth_url}"
            )

        # Prepare headers
        headers = (
            self.custom_auth_request.headers.copy()
            if self.custom_auth_request.headers
            else {}
        )

        # Set Content-Type based on body type if not explicitly set
        if "Content-Type" not in headers:
            if self.custom_auth_request.bodyForm:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                logger.debug(
                    "CustomAuth: Set Content-Type to application/x-www-form-urlencoded"
                )
            elif self.custom_auth_request.body:
                headers["Content-Type"] = "application/json"
                logger.debug("CustomAuth: Set Content-Type to application/json")

        # Prepare request data
        json_data = None
        content = None
        if self.custom_auth_request.body:
            json_data = self.custom_auth_request.body
            logger.debug("CustomAuth: Using JSON body for authentication request")
        elif self.custom_auth_request.bodyForm:
            content = self.custom_auth_request.bodyForm
            logger.debug(
                "CustomAuth: Using form-encoded body for authentication request"
            )

        # Prepare query parameters
        params = self.custom_auth_request.queryParams or {}
        if params:
            logger.debug(f"CustomAuth: Using query parameters: {list(params.keys())}")

        # Make the authentication request using sync client (blocking)
        method = self.custom_auth_request.method
        logger.info(
            f"CustomAuth: Making {method} request to {auth_url} for authentication"
        )
        with httpx.Client(verify=self.verify_ssl, timeout=30.0) as sync_client:
            response = sync_client.request(
                method=method,
                url=auth_url,
                headers=headers,
                params=params,
                json=json_data,
                content=content,
            )
            logger.debug(
                f"CustomAuth: Authentication response status: {response.status_code}"
            )
            response.raise_for_status()

            # Store response
            self.auth_response = response.json()
            logger.info("CustomAuth: Stored authentication response")

    async def reauthenticate(self) -> None:
        """Re-authenticate when token expires (401) - async wrapper for sync authenticate"""
        async with self._lock:
            logger.info("CustomAuth: Starting re-authentication due to 401 error")
            # Clear existing token before re-authenticating
            self.token = None
            logger.debug("CustomAuth: Cleared existing token")
            # Run sync authenticate in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.authenticate)
            logger.info("CustomAuth: Re-authentication completed successfully")

    async def apply_auth_to_request(
        self,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, str], Dict[str, Any], Optional[Dict[str, Any]]]:
        """Apply authentication values to request headers, query params, and body using templates.

        Evaluates templates like {{.access_token}} in headers, queryParams, and body from
        customAuthResponse config using values from the authentication response.

        Returns:
            Tuple of (updated_headers, updated_query_params, updated_body)
        """
        if not self.auth_response or not self.custom_auth_response:
            return headers, query_params or {}, body

        # Evaluate templates in headers from customAuthResponse config
        updated_headers = headers.copy()
        if self.custom_auth_response.headers:
            evaluated_headers = await _evaluate_templates_in_dict(
                self.custom_auth_response.headers, self.auth_response
            )
            # Merge with existing headers (response config headers take precedence)
            updated_headers = {**updated_headers, **evaluated_headers}

        # Evaluate templates in query params from customAuthResponse config
        updated_query_params = query_params.copy() if query_params else {}
        if self.custom_auth_response.queryParams:
            evaluated_params = await _evaluate_templates_in_dict(
                self.custom_auth_response.queryParams, self.auth_response
            )
            # Merge with existing query params (response config params take precedence)
            updated_query_params = {**updated_query_params, **evaluated_params}

        # Evaluate templates in body from customAuthResponse config
        updated_body = body.copy() if body else {}
        if self.custom_auth_response.body:
            evaluated_body = await _evaluate_templates_in_dict(
                self.custom_auth_response.body, self.auth_response
            )
            # Merge with existing body (response config body takes precedence)
            updated_body = {**updated_body, **evaluated_body}

        return (
            updated_headers,
            updated_query_params,
            updated_body if updated_body else None,
        )


# Registry of available auth handlers
AUTH_HANDLERS = {
    "bearer_token": BearerTokenAuth,
    "api_key": ApiKeyAuth,
    "basic": BasicAuth,
    "none": NoAuth,
}


def get_auth_handler(
    auth_type: str,
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    custom_auth_request: Optional[CustomAuthRequestConfig] = None,
    custom_auth_response: Optional[CustomAuthResponseConfig] = None,
) -> AuthHandler:
    """Get the appropriate authentication handler"""
    if auth_type == "custom":
        return CustomAuth(client, config, custom_auth_request, custom_auth_response)
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
            [str, str, Dict[str, Any], Dict[str, str], Optional[Dict[str, Any]]],
            Awaitable[httpx.Response],
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
        body: Optional[Dict[str, Any]] = None,
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
        body: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenType[List[Dict[str, Any]], None]:
        response = await self.make_request(url, method, params, headers, body)
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
        body: Optional[Dict[str, Any]] = None,
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

            response = await self.make_request(
                url, method, current_params, headers, body
            )
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
        body: Optional[Dict[str, Any]] = None,
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

            response = await self.make_request(
                url, method, current_params, headers, body
            )
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
        body: Optional[Dict[str, Any]] = None,
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

            response = await self.make_request(
                url, method, current_params, headers, body
            )
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
        [str, str, Dict[str, Any], Dict[str, str], Optional[Dict[str, Any]]],
        Awaitable[httpx.Response],
    ],
    get_nested_value_fn: Callable[[Dict[str, Any], str], Any],
) -> PaginationHandler:
    """Get the appropriate pagination handler"""
    handler_class = PAGINATION_HANDLERS.get(pagination_type, NonePagination)
    return handler_class(
        client, config, extract_items_fn, make_request_fn, get_nested_value_fn
    )
