from typing import Any, Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client
import ijson
import aiofiles
import base64
import uuid
from port_ocean.core.integrations.mixins.utils import _AiterReader


from gitlab.clients.auth_client import AuthClient


class HTTPBaseClient:
    def __init__(self, base_url: str, token: str, endpoint: str):
        self.token = token
        self._client = http_async_client
        auth_client = AuthClient(token)
        self._headers = auth_client.get_headers()
        self.base_url = f"{base_url}/{endpoint.strip('/')}"

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"
        logger.debug(f"Sending {method} request to {url}")

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json=data,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            result = self._handle_status_code_error(method, path, url, e)
            if result is not None:
                return result
            raise

        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {method} request to {path}: {e}")
            raise

    def _handle_status_code_error(self, method: str, path: str, url: str, e: httpx.HTTPStatusError) -> dict[str, Any] | None:
        status_code = e.response.status_code
        if status_code in (401, 403, 404):
            logger.warning(
                    f"Resource access error at {url} (status {status_code}): {e.response.text}"
                )
            return {}
        logger.error(f"HTTP status error for {method} request to {path}: {e}")
        return None

    async def download_decoded_content(self, path: str, params: Optional[dict[str, Any]] = None, content_key: str = "content"):
            url = f"{self.base_url}/{path}"
            logger.debug(f"Downloading decoded content from {url}")

            try:
                async with self._client.stream("GET", url, params=params, headers=self._headers) as r:
                    r.raise_for_status()
                    reader = _AiterReader(r.iter_bytes())
                    # ijson can parse from an async byte iterator via ijson.asyncio
                    parser = ijson.items(reader, content_key)
                    os.makedirs("/tmp/ocean", exist_ok=True)
                    out_path = f"/tmp/ocean/bulk_{uuid.uuid4()}.json"
                    async with aiofiles.open(out_path, "wb") as f:
                        for content_b64 in parser:
                            # For very long base64, decode in chunks:
                            for i in range(0, len(content_b64), 4*1024*1024):
                                chunk = content_b64[i:i+4*1024*1024]
                                await f.write(base64.b64decode(chunk, validate=True))
                    return out_path
            except httpx.HTTPStatusError as e:
                result = self._handle_status_code_error("GET", path, url, e)
                if result is not None:
                    return result
                raise

            except httpx.HTTPError as e:
                logger.error(f"HTTP error for GET request to {path}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error for download_decoded_content to {path}: {e}")
                raise
