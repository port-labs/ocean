from typing import Optional, Any, AsyncContextManager, cast
import asyncio
from loguru import logger
import aioboto3
from aiobotocore.session import AioSession
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError
from aws.auth.account import AWSSessionStrategy


class SessionCreationError(Exception):
    """Raised when AWS session creation fails after retries."""


class SessionManager:
    """Centralized session management with retries."""

    def __init__(
        self,
        credentials: AWSSessionStrategy,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._credentials = credentials
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def get_session(
        self,
        region: Optional[str] = None,
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioSession:
        """Get a session with retry logic."""
        for attempt in range(self._max_retries):
            try:
                if role_arn is not None:
                    session = await self._credentials.provider.get_session(
                        region=region,
                        role_arn=role_arn,
                        role_session_name=role_session_name,
                    )
                else:
                    session = await self._credentials.provider.get_session(
                        region=region
                    )
                return session
            except ClientError as e:
                if attempt == self._max_retries - 1:
                    logger.error(
                        f"Failed to create session after {self._max_retries} attempts: {e}"
                    )
                    raise
                await asyncio.sleep(self._retry_delay * (attempt + 1))
        raise SessionCreationError("Failed to create AWS session after retries.")
