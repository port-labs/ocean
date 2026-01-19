"""
Ocean Custom Client Factory

Factory function to create HTTP client instances from Ocean configuration.
Supports shared client singleton for parallel-safe operation.
"""

import os
import re
import asyncio
from typing import Dict, Any, Optional

from pydantic import parse_raw_as, parse_obj_as

from http_server.client import HttpServerClient
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.handlers import _validate_templates_in_dict
from http_server.exceptions import (
    CustomAuthConfigError,
    CustomAuthRequestError,
    CustomAuthResponseError,
    TemplateSyntaxError,
)
from port_ocean.context.ocean import ocean

# Module-level shared client singleton
_shared_client: Optional[HttpServerClient] = None
_auth_complete = asyncio.Event()
_auth_in_progress = False
_auth_lock = asyncio.Lock()


def _resolve_env_vars(value: str) -> str:
    """Resolve environment variable references in string (e.g., ${VAR_NAME})"""

    def replace_env(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))  # Return original if not found

    return re.sub(r"\$\{([^}]+)\}", replace_env, value)


def _parse_custom_headers(headers_config: Optional[str]) -> Dict[str, str]:
    """Parse custom headers JSON using Ocean's Pydantic utilities and resolve environment variable references"""
    if not headers_config:
        return {}

    try:
        # Use Ocean's Pydantic parse_raw_as (same as used in Ocean's config parsing)
        headers_dict = parse_raw_as(Dict[str, Any], headers_config)

        # Resolve environment variable references in values
        resolved_headers = {}
        for key, value in headers_dict.items():
            if isinstance(value, str):
                resolved_headers[key] = _resolve_env_vars(value)
            else:
                resolved_headers[key] = str(value)

        return resolved_headers
    except Exception as e:
        raise CustomAuthConfigError(f"Invalid custom_headers JSON: {e}")


def init_client() -> HttpServerClient:
    """Initialize Ocean Custom client from Ocean configuration"""
    config = ocean.integration_config

    # Parse custom headers from config
    custom_headers = _parse_custom_headers(config.get("custom_headers"))

    # Parse and validate custom auth request and response if auth_type is custom
    custom_auth_request = None
    custom_auth_response = None
    auth_type = config.get("auth_type", "none")
    if auth_type == "custom":
        # Parse custom auth request
        custom_auth_request_config = config.get("custom_auth_request")
        if custom_auth_request_config:
            # Handle both dict and string (JSON string) formats
            if isinstance(custom_auth_request_config, str):
                custom_auth_request = parse_raw_as(
                    CustomAuthRequestConfig, custom_auth_request_config
                )
            else:
                custom_auth_request = parse_obj_as(
                    CustomAuthRequestConfig, custom_auth_request_config
                )
        else:
            raise CustomAuthRequestError(
                "customAuthRequest is required when authType is 'custom'"
            )

        # Parse custom auth response (this will validate that at least one field is provided)
        custom_auth_response_config = config.get("custom_auth_response")
        if custom_auth_response_config is not None:
            # Handle both dict and string (JSON string) formats
            if isinstance(custom_auth_response_config, str):
                custom_auth_response = parse_raw_as(
                    CustomAuthResponseConfig, custom_auth_response_config
                )
            else:
                custom_auth_response = parse_obj_as(
                    CustomAuthResponseConfig, custom_auth_response_config
                )
        else:
            raise CustomAuthResponseError(
                "customAuthResponse is required when authType is 'custom'"
            )

        # Validate template syntax BEFORE authentication (fail fast)
        # This catches configuration errors before making any HTTP requests
        if custom_auth_response:
            try:
                if custom_auth_response.headers:
                    _validate_templates_in_dict(custom_auth_response.headers, "headers")
                if custom_auth_response.queryParams:
                    _validate_templates_in_dict(
                        custom_auth_response.queryParams, "queryParams"
                    )
                if custom_auth_response.body:
                    _validate_templates_in_dict(custom_auth_response.body, "body")
            except TemplateSyntaxError as e:
                raise TemplateSyntaxError(
                    f"Invalid template syntax in customAuthResponse: {str(e)}. "
                    "Please fix template syntax before authentication."
                ) from e

    return HttpServerClient(
        base_url=config["base_url"],
        auth_type=auth_type,
        auth_config=config,
        pagination_config=config,
        verify_ssl=config.get("verify_ssl", True),
        max_concurrent_requests=int(config.get("max_concurrent_requests", 10)),
        custom_headers=custom_headers,
        custom_auth_request=custom_auth_request,
        custom_auth_response=custom_auth_response,
        skip_setup=True,  # Don't authenticate here - will be done in @ocean.on_start()
    )


async def get_client() -> HttpServerClient:
    """Get the shared client instance, ensuring authentication is complete.

    This function will wait for authentication to complete if it's in progress,
    or trigger authentication if it hasn't started yet.

    Raises:
        RuntimeError: If client initialization fails
    """
    global _shared_client, _auth_complete, _auth_in_progress, _auth_lock

    from loguru import logger

    # If client exists and auth is complete, return immediately
    if _shared_client is not None and _auth_complete.is_set():
        logger.debug("Client already initialized and authenticated")
        return _shared_client

    # Wait for authentication to complete if it's in progress
    if _auth_in_progress:
        logger.debug("Authentication in progress, waiting for completion...")
        await _auth_complete.wait()
        if _shared_client is None:
            raise RuntimeError("Authentication completed but client is None")
        logger.debug("Authentication completed, returning client")
        return _shared_client

    # If client doesn't exist, initialize and authenticate
    async with _auth_lock:
        # Double-check after acquiring lock (another coroutine might have initialized it)
        if _shared_client is not None and _auth_complete.is_set():
            return _shared_client

        if _auth_in_progress:
            logger.debug("Authentication started by another coroutine, waiting...")
            await _auth_complete.wait()
            if _shared_client is None:
                raise RuntimeError("Authentication completed but client is None")
            return _shared_client

        # Initialize and authenticate (sets _auth_in_progress internally)
        logger.debug("Starting client initialization and authentication...")
        try:
            # This will set _auth_in_progress = True and complete authentication
            await initialize_and_authenticate()
            # Double-check auth is complete (should already be set by initialize_and_authenticate)
            if not _auth_complete.is_set():
                logger.warning("Auth complete event not set, waiting...")
                await _auth_complete.wait()
            # At this point, _shared_client should be set by initialize_and_authenticate
            if _shared_client is None:
                raise RuntimeError("Client initialization returned None")
            # Verify auth handler has auth_response for custom auth
            if (
                _shared_client.auth_type == "custom"
                and hasattr(_shared_client.auth_handler, "auth_response")
                and _shared_client.auth_handler.auth_response is None
            ):
                raise RuntimeError(
                    "Authentication completed but auth_response is None in handler. "
                    "This indicates authentication did not complete properly."
                )
            logger.debug(
                "Client initialization and authentication completed successfully"
            )
            return _shared_client
        except Exception as e:
            _auth_in_progress = False
            _auth_complete.clear()
            logger.error(f"Failed to initialize client: {e}")
            raise RuntimeError(f"Failed to initialize client: {e}") from e


async def initialize_and_authenticate() -> HttpServerClient:
    """Initialize shared client and authenticate if using custom auth.

    This should be called from @ocean.on_start() hook to ensure
    authentication happens once before any resync operations.
    Can also be called from get_client() if authentication hasn't started.

    Returns:
        HttpServerClient: The initialized and authenticated client
    """
    global _shared_client, _auth_in_progress, _auth_complete

    if _shared_client is not None and _auth_complete.is_set():
        return _shared_client

    from loguru import logger

    # Set flag immediately to prevent race conditions
    _auth_in_progress = True

    try:
        logger.debug("Initializing shared HTTP client")
        _shared_client = init_client()

        # Authenticate if using custom auth
        if _shared_client.auth_type == "custom":
            logger.debug("Performing initial authentication for custom auth")
            if hasattr(_shared_client.auth_handler, "authenticate_async"):
                await _shared_client.auth_handler.authenticate_async()
            else:
                logger.warning(
                    "Custom auth handler does not support async authentication"
                )

        logger.debug("Shared HTTP client initialized and authenticated")
        _auth_complete.set()
        return _shared_client
    except Exception as e:
        _auth_in_progress = False
        _auth_complete.clear()
        logger.error(f"Failed to initialize and authenticate client: {e}")
        raise
