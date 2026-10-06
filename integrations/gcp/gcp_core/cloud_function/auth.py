import asyncio
import typing

import google.auth.transport.requests
import google.oauth2.id_token
from loguru import logger


async def get_id_token(audience: str) -> typing.Optional[str]:
    try:
        request = google.auth.transport.requests.Request()
        return await asyncio.to_thread(
            google.oauth2.id_token.fetch_id_token, request, audience
        )
    except Exception as e:
        logger.warning(f"Failed to fetch GCP ID token for {audience!r}: {e}")
        return None
