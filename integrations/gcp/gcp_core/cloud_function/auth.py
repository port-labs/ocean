import asyncio
import typing

from loguru import logger


async def get_id_token(audience: str) -> typing.Optional[str]:
    """Fetch a GCP OIDC ID token for the given audience (Cloud Run URL) using ADC."""
    import google.auth.transport.requests
    import google.oauth2.id_token

    try:
        request = google.auth.transport.requests.Request()
        return await asyncio.to_thread(
            google.oauth2.id_token.fetch_id_token, request, audience
        )
    except Exception as e:
        logger.warning(f"Failed to fetch GCP ID token for {audience!r}: {e}")
        return None
