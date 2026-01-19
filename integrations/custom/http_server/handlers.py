"""
Handlers for HTTP Server integration.

Provides authentication and pagination handlers using strategy pattern.
"""

import asyncio
import httpx
import re
import json
import time

from typing import Dict, Any, List, Callable, Awaitable, Optional
from collections.abc import AsyncGenerator as AsyncGenType

from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from loguru import logger
from port_ocean.context.ocean import ocean

# Module-level lock for re-authentication (shared across all instances)
_reauthenticate_lock = asyncio.Lock()


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
        self.base_url: str = config.get("base_url", "")
        self.auth_response: Optional[Dict[str, Any]] = None
        self.verify_ssl: bool = config.get("verify_ssl", True)

        # Cache for evaluated templates to avoid re-evaluating on every request
        # Cache is invalidated when auth_response changes
        self._cached_auth_response_hash: Optional[str] = None
        self._cached_evaluated_headers: Optional[Dict[str, str]] = None
        self._cached_evaluated_query_params: Optional[Dict[str, Any]] = None
        self._cached_evaluated_body: Optional[Dict[str, Any]] = None

        # Token expiration tracking
        self._auth_timestamp: Optional[float] = None  # When authentication happened
        self._reauthenticate_interval: Optional[int] = (
            None  # How long until re-auth needed (seconds)
        )
        self._reauthenticate_buffer_seconds: int = (
            60  # Buffer to refresh before expiration
        )

    def setup(self) -> None:
        """Setup authentication - deprecated, use authenticate_async() instead.

        This method is kept for backward compatibility but should not be used
        in new code. Authentication should be done via authenticate_async() in
        @ocean.on_start() hook.
        """
        if not self.custom_auth_request:
            logger.debug(
                "CustomAuth: No custom_auth_request configured, skipping setup"
            )
            return
        logger.warning(
            "CustomAuth: setup() is deprecated. Use authenticate_async() in @ocean.on_start() instead."
        )
        # For backward compatibility, run async authenticate in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use run_until_complete
                # This is a fallback for old code
                logger.warning(
                    "CustomAuth: Event loop is running, authentication may fail. "
                    "Please use authenticate_async() instead."
                )
            else:
                loop.run_until_complete(self.authenticate_async())
        except RuntimeError:
            # No event loop - create one
            asyncio.run(self.authenticate_async())

    async def authenticate_async(self) -> None:
        """Make authentication request asynchronously and store token (non-blocking)"""
        if not self.custom_auth_request:
            raise ValueError("customAuthRequest configuration is required")

        logger.info("CustomAuth: Starting authentication")

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
            elif self.custom_auth_request.body:
                headers["Content-Type"] = "application/json"

        # Prepare request data
        json_data = None
        content = None
        if self.custom_auth_request.body:
            json_data = self.custom_auth_request.body
        elif self.custom_auth_request.bodyForm:
            content = self.custom_auth_request.bodyForm

        # Prepare query parameters
        params = self.custom_auth_request.queryParams or {}

        # Make the authentication request using async client (non-blocking)
        method = self.custom_auth_request.method
        logger.debug(
            f"CustomAuth: Making {method} request to {auth_url} for authentication"
        )

        async with httpx.AsyncClient(
            verify=self.verify_ssl, timeout=30.0
        ) as async_client:
            response = await async_client.request(
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
            # Invalidate cache when auth_response changes
            self._invalidate_cache()

            # Track authentication timestamp and calculate expiration interval
            self._auth_timestamp = time.time()
            self._reauthenticate_interval = (
                await self._calculate_reauthenticate_interval()
            )

            logger.info("CustomAuth: Authentication successful")
            if self._reauthenticate_interval:
                logger.debug(
                    f"CustomAuth: Token will expire in {self._reauthenticate_interval} seconds "
                    f"(will refresh {self._reauthenticate_buffer_seconds} seconds before expiration)"
                )
            else:
                logger.debug(
                    "CustomAuth: No expiration interval configured - tokens will only be refreshed on 401 errors"
                )
            if isinstance(self.auth_response, dict):
                # Log first few characters of values (for security, don't log full tokens)
                sample_values = {
                    k: (str(v)[:20] + "..." if len(str(v)) > 20 else str(v))
                    for k, v in list(self.auth_response.items())[:5]
                }
                logger.debug(
                    f"CustomAuth: Auth response sample values: {sample_values}"
                )

    async def reauthenticate(self) -> None:
        """Re-authenticate when token expires (401) - uses module-level lock for thread safety.

        If multiple requests get 401 simultaneously, only the first one will re-authenticate.
        Others will wait for the lock and then skip re-auth if it was already completed.
        """
        # Store current auth_response before waiting for lock
        auth_response_before = self.auth_response

        # Use module-level lock to prevent concurrent re-auth across all instances
        async with _reauthenticate_lock:
            # Check if another coroutine already re-authenticated while we were waiting
            if (
                self.auth_response is not None
                and self.auth_response != auth_response_before
            ):
                logger.debug(
                    "CustomAuth: Auth was already refreshed by another request, skipping redundant re-authentication"
                )
                return

            logger.info("CustomAuth: Starting re-authentication due to 401 error")
            # Clear existing token before re-authenticating
            self.token = None
            # Cache will be invalidated in authenticate_async() when auth_response is updated
            await self.authenticate_async()
            logger.info("CustomAuth: Re-authentication completed successfully")

    def _get_auth_response_hash(self) -> Optional[str]:
        """Generate a hash of the current auth_response for cache invalidation.

        Uses JSON serialization with sorted keys to ensure consistent hashing.
        Returns None if auth_response is None.
        """
        if not self.auth_response:
            return None
        try:
            # Sort keys to ensure consistent hashing regardless of dict order
            return json.dumps(self.auth_response, sort_keys=True)
        except (TypeError, ValueError) as e:
            # If serialization fails (e.g., non-serializable types), return None to force re-evaluation
            logger.warning(f"CustomAuth: Failed to hash auth_response for cache: {e}")
            return None

    def _invalidate_cache(self) -> None:
        """Invalidate the template evaluation cache when auth_response changes."""
        self._cached_auth_response_hash = None
        self._cached_evaluated_headers = None
        self._cached_evaluated_query_params = None
        self._cached_evaluated_body = None

    async def _calculate_reauthenticate_interval(self) -> Optional[int]:
        """Calculate how long until re-authentication is needed.

        Returns:
            Interval in seconds if reauthenticate_interval_seconds is configured, None otherwise
        """
        if (
            self.custom_auth_request
            and self.custom_auth_request.reauthenticate_interval_seconds is not None
        ):
            return self.custom_auth_request.reauthenticate_interval_seconds

        # No expiration interval configured
        logger.debug(
            "CustomAuth: No reauthenticate_interval configured. "
            "Token expiration checking will be disabled."
        )
        return None

    def _is_auth_expired(self) -> bool:
        """Check if authentication has expired and needs to be refreshed.

        Returns:
            True if authentication is expired or about to expire (within buffer), False otherwise.
            Returns False if no expiration interval is configured (expiration checking disabled).
        """
        # If no authentication yet, consider it "expired" to trigger initial auth
        if self._auth_timestamp is None or self.auth_response is None:
            return True

        # If no expiration interval configured, don't check expiration proactively
        # (will still handle 401 errors reactively)
        if self._reauthenticate_interval is None:
            return False

        elapsed_time = time.time() - self._auth_timestamp
        time_until_expiration = self._reauthenticate_interval - elapsed_time

        # Consider expired if within buffer seconds of expiration
        is_expired = time_until_expiration <= self._reauthenticate_buffer_seconds

        if is_expired:
            logger.debug(
                f"CustomAuth: Authentication expired or expiring soon. "
                f"Elapsed: {elapsed_time:.1f}s, Interval: {self._reauthenticate_interval}s, "
                f"Time until expiration: {time_until_expiration:.1f}s"
            )

        return is_expired

    async def _get_evaluated_templates(
        self,
    ) -> tuple[Dict[str, str], Dict[str, Any], Dict[str, Any]]:
        """Get evaluated templates from customAuthResponse config, using cache if available.

        Returns:
            Tuple of (evaluated_headers, evaluated_query_params, evaluated_body)
        """
        if not self.auth_response or not self.custom_auth_response:
            return {}, {}, {}

        # Check if cache is valid
        current_hash = self._get_auth_response_hash()
        if (
            current_hash is not None
            and self._cached_auth_response_hash == current_hash
            and self._cached_evaluated_headers is not None
            and self._cached_evaluated_query_params is not None
            and self._cached_evaluated_body is not None
        ):
            logger.debug("CustomAuth: Using cached evaluated templates")
            return (
                self._cached_evaluated_headers,
                self._cached_evaluated_query_params,
                self._cached_evaluated_body,
            )

        # Cache miss or invalid - evaluate templates
        logger.debug("CustomAuth: Evaluating templates (cache miss or invalid)")

        # Evaluate headers
        evaluated_headers = {}
        if self.custom_auth_response.headers:
            evaluated_headers = await _evaluate_templates_in_dict(
                self.custom_auth_response.headers, self.auth_response
            )

        # Evaluate query params
        evaluated_query_params = {}
        if self.custom_auth_response.queryParams:
            evaluated_query_params = await _evaluate_templates_in_dict(
                self.custom_auth_response.queryParams, self.auth_response
            )

        # Evaluate body
        evaluated_body = {}
        if self.custom_auth_response.body:
            evaluated_body = await _evaluate_templates_in_dict(
                self.custom_auth_response.body, self.auth_response
            )

        # Update cache
        self._cached_auth_response_hash = current_hash
        self._cached_evaluated_headers = evaluated_headers
        self._cached_evaluated_query_params = evaluated_query_params
        self._cached_evaluated_body = evaluated_body

        return evaluated_headers, evaluated_query_params, evaluated_body

    async def apply_auth_to_request(
        self,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, str], Dict[str, Any], Optional[Dict[str, Any]]]:
        """Apply authentication values to request headers, query params, and body using templates.

        Evaluates templates like {{.access_token}} in headers, queryParams, and body from
        customAuthResponse config using values from the authentication response.
        Uses caching to avoid re-evaluating templates on every request when auth_response hasn't changed.
        Proactively re-authenticates if token is expired or about to expire.

        Returns:
            Tuple of (updated_headers, updated_query_params, updated_body)
        """
        # Check if authentication is expired and re-authenticate proactively
        if self._is_auth_expired():
            logger.info(
                "CustomAuth: Token expired or expiring soon, proactively re-authenticating"
            )
            # Use module-level lock to prevent concurrent re-auth
            async with _reauthenticate_lock:
                # Double-check after acquiring lock (another coroutine might have refreshed)
                if self._is_auth_expired():
                    await self.authenticate_async()
                else:
                    logger.debug(
                        "CustomAuth: Token was refreshed by another request while waiting for lock"
                    )

        if not self.auth_response:
            logger.warning(
                "CustomAuth: No auth_response available, skipping auth application"
            )
            return headers, query_params or {}, body

        if not self.custom_auth_response:
            logger.warning(
                "CustomAuth: No custom_auth_response config, skipping auth application"
            )
            return headers, query_params or {}, body

        # Get evaluated templates (from cache if available)
        evaluated_headers, evaluated_query_params, evaluated_body = (
            await self._get_evaluated_templates()
        )

        # Merge evaluated templates with incoming request parameters
        # Response config values take precedence over incoming values
        updated_headers = {**headers, **evaluated_headers}
        updated_query_params = {**(query_params or {}), **evaluated_query_params}

        # Merge body - start with incoming body, then merge evaluated body
        updated_body = (
            {**(body or {}), **evaluated_body} if (body or evaluated_body) else None
        )

        return (
            updated_headers,
            updated_query_params,
            updated_body,
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
