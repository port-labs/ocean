from typing import Any, Dict, List, Optional, Type
import asyncio
from loguru import logger
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter


class TokenRateLimiterContext:
    """
    Async context manager that handles token rotation and rate limiting atomically.

    This context manager:
    1. Finds an available token (rotating if necessary)
    2. Acquires the rate limiter for that token
    3. Provides access to the selected token
    4. Ensures proper cleanup on exit
    """

    def __init__(self, token_manager: "TokenManager"):
        self.token_manager = token_manager
        self.selected_token: str = ""
        self.rate_limiter: Optional[RollingWindowLimiter] = None

    async def __aenter__(self) -> "TokenRateLimiterContext":
        """Enter the context manager: find available token and acquire rate limiter."""
        # Find available token (with rotation if needed)
        async with self.token_manager._lock:
            attempts = 0
            start_index = self.token_manager.current_index

            while attempts < len(self.token_manager.tokens):
                current_token = self.token_manager.tokens[
                    self.token_manager.current_index
                ]
                current_limiter = self.token_manager.rate_limiters[current_token]

                # Check if we can acquire without consuming a slot
                can_acquire = await current_limiter.can_acquire()

                if can_acquire:
                    logger.debug(
                        f"Token {self.token_manager.current_index} has available rate limit quota"
                    )
                    self.selected_token = current_token
                    self.rate_limiter = current_limiter
                    break
                else:
                    logger.info(
                        f"Rate limit exhausted for token index {self.token_manager.current_index}, rotating to next token"
                    )
                    self.token_manager._rotate_to_next_token()
                    attempts += 1

            # If all tokens are rate limited, use the first one and wait normally
            if not self.selected_token:
                logger.info(
                    "All tokens are rate limited, returning to first token to wait normally"
                )
                self.token_manager.current_index = start_index
                current_token = self.token_manager.tokens[
                    self.token_manager.current_index
                ]
                self.selected_token = current_token
                self.rate_limiter = self.token_manager.rate_limiters[current_token]

        # Acquire the rate limiter slot (this may wait if rate limited)
        if self.rate_limiter:
            await self.rate_limiter.acquire()

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit the context manager: release the rate limiter."""
        self.release()

    def release(self) -> None:
        """Release any held resources. Since rate limiter uses rolling window, no explicit release needed."""
        # The RollingWindowLimiter doesn't require explicit release
        # as it tracks usage automatically via timestamps
        pass

    def get_token(self) -> str:
        """Get the token selected by this context manager."""
        return self.selected_token


class TokenManager:
    """
    Manages multiple workspace tokens with automatic rotation when rate limits are hit.

    This class is async-safe and prevents race conditions using asyncio.Lock.
    Uses the can_acquire() method to check availability without consuming rate limit slots.
    """

    def __init__(self, tokens: List[str], limit: int, window: int):
        self.tokens = tokens
        self.current_index = 0
        self.rate_limiters: Dict[str, RollingWindowLimiter] = {}
        self._lock = asyncio.Lock()

        for token in tokens:
            self.rate_limiters[token] = RollingWindowLimiter(
                limit=limit,
                window=window,
            )

    @property
    def current_token(self) -> str:
        """Get the current token. Note: This can change during async operations."""
        return self.tokens[self.current_index]

    @property
    def current_rate_limiter(self) -> RollingWindowLimiter:
        """Get the rate limiter for the current token. Note: This can change during async operations."""
        return self.rate_limiters[self.current_token]

    def _rotate_to_next_token(self) -> None:
        """
        Rotate to the next token in the list.

        Note: This method should only be called while holding self._lock
        """
        old_index = self.current_index
        self.current_index = (self.current_index + 1) % len(self.tokens)
        logger.debug(f"Rotated from token index {old_index} to {self.current_index}")

    async def get_current_token_safely(self) -> str:
        async with self._lock:
            return self.tokens[self.current_index]

    async def get_token_metrics(self) -> Dict[str, Dict[str, Any]]:
        async with self._lock:
            metrics = {}
            for i, token in enumerate(self.tokens):
                rate_limiter = self.rate_limiters[token]
                metrics[f"token_{i}"] = {
                    "token_masked": f"{token[:8]}..." if len(token) > 8 else token,
                    "is_current": i == self.current_index,
                    "metrics": rate_limiter.get_metrics(),
                }
            return metrics
