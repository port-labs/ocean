from typing import Optional, AsyncIterator, Any
from loguru import logger
from .auth_client import AuthClient
from port_ocean.utils import http_async_client


class RestClient:

    def __init__(self, base_url: str, auth_client: AuthClient):
        self.base_url = f"{base_url}/api/v4"
        self.auth_client = auth_client
        self._client = http_async_client

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        try:
            url = f"{self.base_url}/{path}"
            response = await self._client.request(
                method=method,
                url=url,
                headers=self.auth_client.get_headers(),
                params=params,
                json=data,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to make {method} request to {path}: {str(e)}")
            raise

    async def make_paginated_request(
        self, path: str, params: Optional[dict[str, Any]] = None, page_size: int = 100
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        params = params or {}

        while True:
            try:
                request_params = {**params, "per_page": page_size, "page": page}

                response = await self.send_api_request(
                    "GET", path, params=request_params
                )

                if not response:
                    break

                yield response

                if len(response) < page_size:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Failed to fetch page {page} from {path}: {str(e)}")
                raise
