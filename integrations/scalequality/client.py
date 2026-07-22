from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client


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

    async def get_entities(self) -> list[dict[Any, Any]]:
        """Fetch every org, business unit and team with its quality signals."""
        url = f"{self.base_url}/entities"
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            logger.error(
                f"ScaleQuality API returned {error.response.status_code} for "
                f"{url}: {error.response.text}"
            )
            raise

        payload: dict[Any, Any] = response.json()
        entities: list[dict[Any, Any]] = payload.get("entities", [])
        logger.info(f"Fetched {len(entities)} entities from ScaleQuality")
        return entities
