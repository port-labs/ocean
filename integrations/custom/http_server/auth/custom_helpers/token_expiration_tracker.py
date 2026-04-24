"""Tracks token expiration and determines when re-authentication is needed."""

import time
from typing import Optional
from loguru import logger


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

    def is_expired(self) -> bool:
        """Check if authentication has expired and needs to be refreshed.

        Returns:
            True if authentication is expired or about to expire (within buffer), False otherwise.
            Returns False if no expiration interval is configured (expiration checking disabled).
        """
        if self._auth_timestamp is None:
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
