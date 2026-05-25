import asyncio
import httpx
from functools import wraps
from typing import Any, Callable
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication


def retry_transient_network(max_attempts: int = 3) -> Callable:
    """Retries async functions explicitly on timeouts and transient network issues."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except (
                    httpx.TimeoutException,  # All httpx timeouts (Read, Write, Connect, Pool)
                    asyncio.TimeoutError,  # Event loop timeouts
                    TimeoutError,  # Python 3.11+ native timeouts
                    httpx.RequestError,  # Other connection drops
                    ConnectionError,  # OS-level connection resets
                    OSError,  # OS-level socket flakiness
                ) as exc:
                    if attempt < max_attempts:
                        logger.warning(
                            f"Timeout/Network error (attempt {attempt}/{max_attempts}): "
                            f"{type(exc).__name__}: {exc}. Retrying in {2 ** attempt}s..."
                        )
                        await asyncio.sleep(2**attempt)
                    else:
                        logger.error(
                            f"Failed HTTP request after {max_attempts} attempts due to timeout/network error: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        return None

                except asyncio.CancelledError:
                    # Let the app shut down cleanly if cancelled
                    raise

                except Exception as exc:
                    # Pure logic bugs (e.g. KeyError, TypeError). Do not retry these.
                    logger.error(
                        f"Unexpected logic error during HTTP request: {type(exc).__name__}: {exc}"
                    )
                    return None

        return wrapper

    return decorator


def _truncate(text: str, max_len: int = 256) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


class OceanHttpClient:
    """
    Manages the underlying httpx client, authentication, and retries.
    Uses lazy initialization to safely support cross-process/subprocess usage.
    """

    def __init__(self, auth: PortAuthentication, timeout: int = 10) -> None:
        self.auth = auth
        self._timeout = timeout
        # Do NOT create the httpx client here.
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-loads the client to ensure it binds to the active event loop."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @retry_transient_network(max_attempts=3)
    async def post(self, url: str, json: dict[str, Any]) -> None:
        """Generic POST request -- best-effort, never raises. Retries on transient/5xx errors."""
        headers = await self.auth.headers()

        # Grab the safely bound client to avoid asyncio subprocess lock issues
        client = self._get_client()

        response = await client.post(url, headers=headers, json=json)

        if response.is_error:
            # Manually raise 5xx errors so the decorator catches and retries them
            if response.status_code >= 500:
                response.raise_for_status()

            escaped = response.text.replace("{", "{{").replace("}", "}}")
            logger.warning(
                f"API returned an error for POST {url}: {_truncate(escaped)}",
                status_code=response.status_code,
                response_body=_truncate(response.text),
            )
        else:
            logger.info(
                f"API request succeeded for POST {url}",
                status_code=response.status_code,
                # Usually you don't need to log the response body on success for all clients,
                # but leaving it here if you want the verbose trail!
                response_body=_truncate(response.text),
            )
