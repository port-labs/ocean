from integrations.spacelift.config import Config
from port_ocean.utils import http_async_client
from fastapi import HTTPException
from integrations.spacelift.utils.logger import logger


config = Config()

async def emit_to_port(kind: str, entity: dict):
    if not config.PORT_CLIENT_ID or not config.PORT_CLIENT_SECRET:
        logger.error("Missing Port credentials.")
        raise RuntimeError("Missing Port credentials")

    try:
        # Step 1: Auth
        token_resp = await http_async_client.post(
            f"{config.PORT_BASE_URL}/auth/access_token",
            json={
                "clientId": config.PORT_CLIENT_ID,
                "clientSecret": config.PORT_CLIENT_SECRET
            }
        )
        token_resp.raise_for_status()
        token = (await token_resp.json())["accessToken"]
    except Exception as e:
        logger.error("Failed to authenticate with Port", exc_info=True)
        raise HTTPException(status_code=500, detail="Port authentication failed")

    # Step 2: Emit entity
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = await http_async_client.post(
            f"{config.PORT_BASE_URL}/blueprints/{kind}/entities",
            headers=headers,
            json={
                "identifier": entity["identifier"],
                "title": entity["title"],
                "properties": entity["properties"]
            }
        )
        response.raise_for_status()
        logger.info(f"Successfully emitted {entity['identifier']} to Port.")
    except Exception:
        logger.error("Failed to emit entity to Port", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to emit to Port")
