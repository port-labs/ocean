import os
import time
from utils.logger import logger
from .config import Config

# Initial token, can be set via environment variable
INITIAL_TOKEN = os.getenv("SPACELIFT_TOKEN", Config.SPACELIFT_TOKEN)

class SpaceliftAuth:
    def __init__(self):
        self.token = INITIAL_TOKEN
        self.token_expires_at = None
        self._parse_token_expiry()

    def _parse_token_expiry(self):
        """
        Optional: parse expiry from token if it's JWT.
        Fallback: set a max TTL for rotation if needed.
        """
        self.token_expires_at = time.time() + 60 * 60 * 3
        logger.debug("Token expiry set to 3 hours from now.")

    def is_expired(self) -> bool:
        if self.token_expires_at is None:
            return False
        return time.time() >= self.token_expires_at

    async def get_headers(self):
        if self.is_expired():
            logger.warning("Spacelift token expired. Refreshing...")
            await self.refresh_token()
        return {"Authorization": f"Bearer {self.token}"}

    async def refresh_token(self):
        """
        Token refresh logic.
        By default, re-reads from env — can be upgraded to pull from a vault, file, or refresh API.
        """
        new_token = os.getenv("SPACELIFT_TOKEN")
        if not new_token:
            logger.error("SPACELIFT_TOKEN not available in env. Cannot refresh.")
            raise RuntimeError("Token refresh failed — no token found.")

        if new_token == self.token:
            logger.warning("SPACELIFT_TOKEN reloaded but unchanged.")

        self.token = new_token
        self._parse_token_expiry()
        logger.info("Spacelift token refreshed.")
