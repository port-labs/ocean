"""
Custom authentication flow with dynamic token retrieval and template evaluation.

Supports custom authentication flows with template-based token injection into requests.
"""

import httpx
import json
from typing import AsyncGenerator, Dict, Any, Optional

from loguru import logger

from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.exceptions import CustomAuthRequestError
from http_server.helpers.template_utils import evaluate_templates_in_dict
from http_server.auth.custom.lock_manager import LockManager
from http_server.auth.custom.template_cache import TemplateCache
from http_server.auth.custom.token_expiration_tracker import TokenExpirationTracker

# Constants
DEFAULT_AUTH_TIMEOUT = 30.0
STATUS_CODES_TO_REAUTH = [401]


class AuthFlowManager(httpx.Auth):
    """Custom authentication with dynamic token retrieval"""

    def __init__(
        self,
        config: Dict[str, Any],
        custom_auth_request: Optional[CustomAuthRequestConfig],
        custom_auth_response: Optional[CustomAuthResponseConfig],
        cache: Optional[TemplateCache] = None,
        expiration_tracker: Optional[TokenExpirationTracker] = None,
        reauth_lock_manager: Optional[LockManager] = None,
    ):
        self.custom_auth_request = custom_auth_request
        self.custom_auth_response = custom_auth_response
        self.base_url: str = config.get("base_url", "")
        self.auth_response: Optional[Dict[str, Any]] = None
        self.verify_ssl: bool = config.get("verify_ssl", True)

        self._cache = cache or TemplateCache()
        self._reauth_lock_manager = reauth_lock_manager or LockManager()

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

    async def _perform_auth_request(self) -> None:
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
            try:
                self.auth_response = response.json()
            except json.JSONDecodeError as e:
                logger.error(
                    f"CustomAuth: Failed to parse authentication response: {str(e)}",
                    {"response": str(response.text)},
                )
                raise
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

    async def _ensure_authenticated(self) -> None:
        """Checks expiration and handles locking for re-auth."""
        if self._expiration_tracker.is_expired():
            async with self._reauth_lock_manager.lock:
                # Re-check after acquiring lock (double-checked locking pattern)
                if self._expiration_tracker.is_expired():
                    await self._perform_auth_request()

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        # 1. Proactive Auth Check (Before sending the request)
        await self._ensure_authenticated()

        # 2. Apply templates to the current request
        authenticated_request = await self._override_request(request)

        # 3. Send the request
        response = yield authenticated_request

        # 4. Reactive Auth Check (On status codes that require re-authentication)
        if response.status_code in STATUS_CODES_TO_REAUTH:
            async with self._reauth_lock_manager.lock:
                # Only re-auth if someone else hasn't already done it while we waited
                await self._perform_auth_request()
                authenticated_request = await self._override_request(request)
                # Re-apply new tokens to the original request
                yield authenticated_request

    async def _override_request(self, request: httpx.Request) -> httpx.Request:
        """Override the request with the evaluated templates."""
        # Always clone the request to avoid modifying the original
        request_clone = httpx.Request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            params=request.url.params,
            content=request.content,
            extensions=request.extensions,
        )

        if self.auth_response:
            eval_headers, eval_query, eval_body = await self._get_evaluated_templates()

            # Update Headers
            if eval_headers:
                for k, v in eval_headers.items():
                    request_clone.headers[k] = v

            if eval_query:
                # Update Query Params
                request_clone.url = request_clone.url.copy_merge_params(eval_query)

            # Update Body (Note: httpx request bodies are bytes, requires re-encoding)
            if eval_body:
                body_bytes = request.read()
                try:
                    current_data = json.loads(body_bytes.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    current_data = {}

                current_data.update(eval_body)
                new_content = json.dumps(current_data).encode("utf-8")
                request_clone._content = new_content
                request_clone.stream = httpx.ByteStream(new_content)
                request_clone.headers["Content-Length"] = str(len(new_content))

        return request_clone

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
