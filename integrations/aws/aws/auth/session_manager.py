from typing import Dict, Optional, Any
import asyncio
from loguru import logger
import aioboto3
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError
from aws.auth.account import AWSSessionStrategy


class SessionManager:
    """Centralized session management with caching and retries."""

    def __init__(
        self,
        credentials: AWSSessionStrategy,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        cache_ttl: int = 300,  # 5 minutes
    ):
        self._credentials = credentials
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._cache_ttl = cache_ttl
        self._session_cache: Dict[str, Any] = {}
        self._client_cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def get_session(
        self,
        region: Optional[str] = None,
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> aioboto3.Session:
        """Get or create a session with caching."""
        cache_key = f"{region}:{role_arn}"

        async with self._lock:
            if cache_key in self._session_cache:
                return self._session_cache[cache_key]

            for attempt in range(self._max_retries):
                try:
                    if role_arn:
                        session = await self._credentials.provider.get_session(
                            region=region,
                            role_arn=role_arn,
                            role_session_name=role_session_name,
                        )
                    else:
                        session = await self._credentials.provider.get_session(
                            region=region
                        )
                    self._session_cache[cache_key] = session
                    return session
                except ClientError as e:
                    if attempt == self._max_retries - 1:
                        logger.error(
                            f"Failed to create session after {self._max_retries} attempts: {e}"
                        )
                        raise
                    await asyncio.sleep(self._retry_delay * (attempt + 1))

    async def get_client(
        self,
        service_name: str,
        region: Optional[str] = None,
        role_arn: Optional[str] = None,
        config: Optional[Boto3Config] = None,
    ) -> Any:
        """Get or create a client with caching."""
        cache_key = f"{service_name}:{region}:{role_arn}"

        async with self._lock:
            if cache_key in self._client_cache:
                return self._client_cache[cache_key]

            session = await self.get_session(region=region, role_arn=role_arn)

            for attempt in range(self._max_retries):
                try:
                    client = await session.client(service_name, config=config)
                    self._client_cache[cache_key] = client
                    return client
                except ClientError as e:
                    if attempt == self._max_retries - 1:
                        logger.error(
                            f"Failed to create client after {self._max_retries} attempts: {e}"
                        )
                        raise
                    await asyncio.sleep(self._retry_delay * (attempt + 1))

    async def clear_cache(self):
        """Clear the session and client caches."""
        async with self._lock:
            self._session_cache.clear()
            self._client_cache.clear()

    async def close(self):
        """Close all cached clients and sessions."""
        async with self._lock:
            for client in self._client_cache.values():
                await client.close()
            self._client_cache.clear()
            self._session_cache.clear()
