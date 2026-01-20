"""
Custom authentication handler with dynamic token retrieval and template evaluation.

Supports custom authentication flows with template-based token injection into requests.
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any, Optional

from loguru import logger

from http_server.auth.base import AuthHandler
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.exceptions import CustomAuthRequestError
from http_server.helpers.template_utils import evaluate_templates_in_dict


class ReauthLockManager:
    """Manages re-authentication lock to prevent concurrent re-auth attempts."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()


class TemplateCache:
    """Manages caching of evaluated templates to avoid re-evaluation on every request."""

    def __init__(self) -> None:
        self._auth_response_hash: Optional[str] = None
        self._evaluated_headers: Optional[Dict[str, str]] = None
        self._evaluated_query_params: Optional[Dict[str, Any]] = None
        self._evaluated_body: Optional[Dict[str, Any]] = None

    def invalidate(self) -> None:
        """Invalidate the cache when auth_response changes."""
        self._auth_response_hash = None
        self._evaluated_headers = None
        self._evaluated_query_params = None
        self._evaluated_body = None

    def is_valid(self, current_hash: Optional[str]) -> bool:
        """Check if cache is valid for the given hash."""
        return (
            current_hash is not None
            and self._auth_response_hash == current_hash
            and self._evaluated_headers is not None
            and self._evaluated_query_params is not None
            and self._evaluated_body is not None
        )

    def get_cached(self) -> tuple[Dict[str, str], Dict[str, Any], Dict[str, Any]]:
        """Get cached evaluated templates."""
        return (
            self._evaluated_headers or {},
            self._evaluated_query_params or {},
            self._evaluated_body or {},
        )

    def update(
        self,
        hash_value: Optional[str],
        headers: Dict[str, str],
        query_params: Dict[str, Any],
        body: Dict[str, Any],
    ) -> None:
        """Update cache with new evaluated templates."""
        self._auth_response_hash = hash_value
        self._evaluated_headers = headers
        self._evaluated_query_params = query_params
        self._evaluated_body = body


class TokenExpirationTracker:
    """Tracks token expiration and determines when re-authentication is needed."""

    def __init__(
        self, reauthenticate_interval: Optional[int] = None, buffer_seconds: int = 60
    ):
        self._auth_timestamp: Optional[float] = None
        self._reauthenticate_interval = reauthenticate_interval
        self._buffer_seconds = buffer_seconds

    def record_authentication(self) -> None:
        """Record that authentication happened."""
        self._auth_timestamp = time.time()

    def is_expired(self, has_auth_response: bool) -> bool:
        """Check if authentication has expired and needs to be refreshed.

        Returns:
            True if authentication is expired or about to expire (within buffer), False otherwise.
            Returns False if no expiration interval is configured (expiration checking disabled).
        """
        if self._auth_timestamp is None or not has_auth_response:
            return True

        if self._reauthenticate_interval is None:
            return False

        elapsed_time = time.time() - self._auth_timestamp
        time_until_expiration = self._reauthenticate_interval - elapsed_time
        is_expired = time_until_expiration <= self._buffer_seconds

        if is_expired:
            logger.debug(
                f"CustomAuth: Authentication expired or expiring soon. "
                f"Elapsed: {elapsed_time:.1f}s, Interval: {self._reauthenticate_interval}s, "
                f"Time until expiration: {time_until_expiration:.1f}s"
            )

        return is_expired

    def get_expiration_info(self) -> tuple[Optional[int], int]:
        """Get expiration interval and buffer seconds."""
        return self._reauthenticate_interval, self._buffer_seconds


# Constants
DEFAULT_AUTH_TIMEOUT = 30.0


class CustomAuth(AuthHandler):
    """Custom authentication with dynamic token retrieval"""

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: Dict[str, Any],
        custom_auth_request: Optional[CustomAuthRequestConfig],
        custom_auth_response: Optional[CustomAuthResponseConfig],
        cache: Optional[TemplateCache] = None,
        expiration_tracker: Optional[TokenExpirationTracker] = None,
        reauth_lock_manager: Optional[ReauthLockManager] = None,
    ):
        super().__init__(client, config)
        self._is_async_setup = True
        self.custom_auth_request = custom_auth_request
        self.custom_auth_response = custom_auth_response
        self.token: Optional[str] = None
        self.base_url: str = config.get("base_url", "")
        self.auth_response: Optional[Dict[str, Any]] = None
        self.verify_ssl: bool = config.get("verify_ssl", True)

        self._cache = cache or TemplateCache()
        self._reauth_lock_manager = reauth_lock_manager or ReauthLockManager()

        # Initialize expiration tracker with interval from config if not provided
        if expiration_tracker is None:
            reauthenticate_interval = (
                custom_auth_request.reauthenticate_interval_seconds
                if custom_auth_request
                else None
            )
            self._expiration_tracker = TokenExpirationTracker(
                reauthenticate_interval=reauthenticate_interval
            )
        else:
            self._expiration_tracker = expiration_tracker

    def setup(self) -> None:
        """Setup authentication - deprecated, use async_setup() instead.

        This method is kept for backward compatibility but should not be used
        in new code. Authentication should be done via async_setup() in
        @ocean.on_start() hook.
        """
        if not self.custom_auth_request:
            logger.debug(
                "CustomAuth: No custom_auth_request configured, skipping setup"
            )
            return
        logger.warning(
            "CustomAuth: setup() is deprecated. Use async_setup() in @ocean.on_start() instead."
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(
                    "CustomAuth: Event loop is running, authentication may fail. "
                    "Please use async_setup() instead."
                )
            else:
                loop.run_until_complete(self.async_setup())
        except RuntimeError:
            asyncio.run(self.async_setup())

    async def async_setup(self) -> None:
        """Setup authentication asynchronously - alias for authenticate_async()"""
        await self.authenticate_async()

    async def authenticate_async(self) -> None:
        """Make authentication request asynchronously and store token (non-blocking)"""
        if not self.custom_auth_request:
            raise CustomAuthRequestError("customAuthRequest configuration is required")

        logger.info("CustomAuth: Starting authentication")

        endpoint = self.custom_auth_request.endpoint
        if endpoint.startswith(("http://", "https://")):
            auth_url = endpoint
            logger.debug(f"CustomAuth: Using full URL for authentication: {auth_url}")
        else:
            base_url = self.base_url.rstrip("/")
            endpoint_path = endpoint.lstrip("/")
            auth_url = f"{base_url}/{endpoint_path}"
            logger.debug(
                f"CustomAuth: Built auth URL from base_url and endpoint: {auth_url}"
            )

        headers = (
            self.custom_auth_request.headers.copy()
            if self.custom_auth_request.headers
            else {}
        )

        if "Content-Type" not in headers:
            if self.custom_auth_request.bodyForm:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            elif self.custom_auth_request.body:
                headers["Content-Type"] = "application/json"

        json_data = None
        content = None
        if self.custom_auth_request.body:
            json_data = self.custom_auth_request.body
        elif self.custom_auth_request.bodyForm:
            content = self.custom_auth_request.bodyForm

        params = self.custom_auth_request.queryParams or {}
        method = self.custom_auth_request.method
        logger.debug(
            f"CustomAuth: Making {method} request to {auth_url} for authentication"
        )

        async with httpx.AsyncClient(
            verify=self.verify_ssl, timeout=DEFAULT_AUTH_TIMEOUT
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

            self.auth_response = response.json()
            self._cache.invalidate()

            self._expiration_tracker.record_authentication()

            logger.info("CustomAuth: Authentication successful")
            interval, buffer = self._expiration_tracker.get_expiration_info()
            if interval:
                logger.debug(
                    f"CustomAuth: Token will expire in {interval} seconds "
                    f"(will refresh {buffer} seconds before expiration)"
                )
            else:
                logger.debug(
                    "CustomAuth: No expiration interval configured - tokens will only be refreshed on 401 errors"
                )

    async def reauthenticate(self) -> None:
        """Re-authenticate when token expires (401) - uses lock manager for thread safety.

        If multiple requests get 401 simultaneously, only the first one will re-authenticate.
        Others will wait for the lock and then skip re-auth if it was already completed.
        """
        auth_response_before = self.auth_response

        async with self._reauth_lock_manager.lock:
            # The check `auth_response != auth_response_before` is necessary because:
            # - Multiple coroutines may detect 401 and enter the lock queue simultaneously
            # - While waiting for the lock, another coroutine may have already re-authenticated
            # - By comparing auth_response before and after acquiring the lock, we detect if
            #   re-authentication already happened and skip redundant work
            if (
                self.auth_response is not None
                and self.auth_response != auth_response_before
            ):
                logger.debug(
                    "CustomAuth: Auth was already refreshed by another request, skipping redundant re-authentication"
                )
                return

            logger.info("CustomAuth: Starting re-authentication due to 401 error")
            self.token = None
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
            return json.dumps(self.auth_response, sort_keys=True)
        except (TypeError, ValueError) as e:
            logger.warning(f"CustomAuth: Failed to hash auth_response for cache: {e}")
            return None

    async def _get_evaluated_templates(
        self,
    ) -> tuple[Dict[str, str], Dict[str, Any], Dict[str, Any]]:
        """Get evaluated templates from customAuthResponse config, using cache if available.

        Returns:
            Tuple of (evaluated_headers, evaluated_query_params, evaluated_body)
        """
        if not self.auth_response or not self.custom_auth_response:
            return {}, {}, {}

        current_hash = self._get_auth_response_hash()
        if self._cache.is_valid(current_hash):
            logger.debug("CustomAuth: Using cached evaluated templates")
            return self._cache.get_cached()

        logger.debug("CustomAuth: Evaluating templates (cache miss or invalid)")

        evaluated_headers = {}
        if self.custom_auth_response.headers:
            evaluated_headers = await evaluate_templates_in_dict(
                self.custom_auth_response.headers, self.auth_response
            )

        evaluated_query_params = {}
        if self.custom_auth_response.queryParams:
            evaluated_query_params = await evaluate_templates_in_dict(
                self.custom_auth_response.queryParams, self.auth_response
            )

        evaluated_body = {}
        if self.custom_auth_response.body:
            evaluated_body = await evaluate_templates_in_dict(
                self.custom_auth_response.body, self.auth_response
            )

        self._cache.update(
            current_hash, evaluated_headers, evaluated_query_params, evaluated_body
        )

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
        if self._expiration_tracker.is_expired(self.auth_response is not None):
            logger.info(
                "CustomAuth: Token expired or expiring soon, proactively re-authenticating"
            )
            async with self._reauth_lock_manager.lock:
                if self._expiration_tracker.is_expired(self.auth_response is not None):
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

        evaluated_headers, evaluated_query_params, evaluated_body = (
            await self._get_evaluated_templates()
        )

        updated_headers = {**headers, **evaluated_headers}
        updated_query_params = {**(query_params or {}), **evaluated_query_params}
        updated_body = (
            {**(body or {}), **evaluated_body} if (body or evaluated_body) else None
        )

        return (
            updated_headers,
            updated_query_params,
            updated_body,
        )
