from typing import Any, Dict, List
import asyncio
from loguru import logger
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from bitbucket_cloud.helpers.utils import BitbucketRateLimiterConfig


class TokenManager:
    """
    Manages multiple workspace tokens with automatic rotation when rate limits are hit.

    This class is async-safe and prevents race conditions using asyncio.Lock.
    Uses the can_acquire() method to check availability without consuming rate limit slots.
    """

    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.current_index = 0
        self.rate_limiters: Dict[str, RollingWindowLimiter] = {}
        self._lock = asyncio.Lock()

        for token in tokens:
            self.rate_limiters[token] = RollingWindowLimiter(
                limit=BitbucketRateLimiterConfig.LIMIT,
                window=BitbucketRateLimiterConfig.WINDOW,
            )

    @property
    def current_token(self) -> str:
        """Get the current token. Note: This can change during async operations."""
        return self.tokens[self.current_index]

    @property
    def current_rate_limiter(self) -> RollingWindowLimiter:
        """Get the rate limiter for the current token. Note: This can change during async operations."""
        return self.rate_limiters[self.current_token]

    async def try_acquire_or_rotate(self) -> RollingWindowLimiter:
        """
        Try to find an available token and return its rate limiter.

        This method uses can_acquire() to check availability without consuming slots,
        then rotates through tokens until finding an available one. If all tokens
        are exhausted, it returns the first token's rate limiter to wait normally.

        Returns the rate limiter to use for the request.
        This method is thread-safe and prevents race conditions.
        """
        async with self._lock:
            attempts = 0
            start_index = self.current_index

            while attempts < len(self.tokens):
                current_token = self.tokens[self.current_index]
                current_limiter = self.rate_limiters[current_token]

                # Check if we can acquire without consuming a slot
                can_acquire = await current_limiter.can_acquire()

                if can_acquire:
                    logger.debug(
                        f"Token {self.current_index} has available rate limit quota"
                    )
                    return current_limiter
                else:
                    logger.info(
                        f"Rate limit exhausted for token index {self.current_index}, rotating to next token"
                    )
                    self._rotate_to_next_token()
                    attempts += 1

                    if attempts >= len(self.tokens):
                        logger.info(
                            "All tokens are rate limited, returning to first token to wait normally"
                        )
                        self.current_index = start_index
                        current_token = self.tokens[self.current_index]
                        return self.rate_limiters[current_token]

            current_token = self.tokens[self.current_index]
            return self.rate_limiters[current_token]

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
