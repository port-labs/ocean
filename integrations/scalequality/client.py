from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

# Cap how much of an upstream error body we copy into logs, so a large or
# verbose error response cannot bloat the log stream or persist unexpected
# upstream detail verbatim.
_MAX_ERROR_BODY = 500


class ScaleQualityClient:
    """Thin async client over the ScaleQuality read-only ``/v1`` API.

    ScaleQuality exposes a single bulk endpoint, ``GET /entities``, which returns
    every organization, business unit and team the API key can see, each already
    enriched with its quality signals. One request is enough for a full resync.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.http_client = http_async_client
        self.http_client.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    async def get_entities(self) -> AsyncGenerator[list[dict[Any, Any]], None]:
        """Yield every org, business unit and team with its quality signals.

        ScaleQuality returns the whole set in one bulk response, so this yields a
        single batch. Using the generator shape keeps the client aligned with
        Ocean's streaming resync contract, so if the API ever grows server-side
        paging the batches flow straight through without touching the resync.
        """
        url = f"{self.base_url}/entities"
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            payload: dict[Any, Any] = response.json()
        except httpx.HTTPStatusError as error:
            body = error.response.text[:_MAX_ERROR_BODY]
            logger.error(
                f"ScaleQuality API returned {error.response.status_code} for "
                f"GET {url}: {body}"
            )
            raise
        except httpx.RequestError as error:
            logger.error(f"ScaleQuality API request failed for GET {url}: {error}")
            raise
        except ValueError as error:
            logger.error(
                f"ScaleQuality API returned invalid JSON for GET {url}: {error}"
            )
            raise

        entities: list[dict[Any, Any]] = payload.get("entities", [])
        logger.info(f"Fetched {len(entities)} entities from ScaleQuality")
        yield entities
