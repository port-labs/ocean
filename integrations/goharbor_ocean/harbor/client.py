"""
Core client module for interacting with GoHarbor's API

Currently:
 - Supports Harbor v2.11.0 API
 - Handles authentication, pagination, rate limiting, and error handling

Maintainer: @50-Course (github.com/50-Course)
Created: 2025-10-12
"""

import asyncio
from typing import Any, Optional, AsyncGenerator
from urllib.parse import quote

from loguru import logger
from httpx import HTTPStatusError, Timeout

from port_ocean.utils.http_async_client import http_async_client

from harbor.exceptions import (
    HarborAPIError,
    InvalidConfigurationError,
    MissingCredentialsError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from harbor.utils.auth import create_basic_auth_header, generate_basic_auth_header
from harbor.utils.constants import (
    API_VERSION,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_CONCURRENT_REQUESTS,
    ENDPOINTS,
    HarborKind,
    ARTIFACT_QUERY_PARAMS,
)


class HarborClient:
    """
    Async HTTP client for Harbor API

    Provides methods for fetching projects, users, repositories, and artifacts
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ):
        """
        Initalizes Harbor API client

        Args:
            base_url: Harbor instance base URL (e.g., https://harbor.example.com)
            username: Harbor username (robot account or user)
            password: Harbor password/token
            verify_ssl: Whether to verify SSL certificates

        Raises:
            InvalidConfigurationError: If base_url is empty
            MissingCredentialsError: If username or password is missing
        """

        if not base_url or not base_url.strip():
            raise InvalidConfigurationError('base_url cannot be empty')

        if not username or username is None:
            raise MissingCredentialsError('username is required')

        if not password or password is None:
            raise MissingCredentialsError('password is required')

        self.base_url = f"{base_url.rstrip('/')}/api/{API_VERSION}"
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

        self.client, self.client.timeout = http_async_client, Timeout(DEFAULT_TIMEOUT)

        auth_header_name, auth_header_value = generate_basic_auth_header(username, password)
        if not hasattr(self.client, 'headers'):
            self.client.headers = {}
        self.client.headers[auth_header_name] = auth_header_value

        # to help us control batch requests
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        # ideally we would want to use structured logging, but it is what it is
        logger.info(
            f'[Ocean][Harbor] Initialized client for {self.base_url} '
            f'(verify_ssl={self.verify_ssl})'
        )
