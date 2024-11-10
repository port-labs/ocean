from typing import List

from loguru import logger

from port_ocean.clients.port.client import PortClient


async def cleanup_integration(client: PortClient, blueprints: List[str]) -> None:
    for blueprint in blueprints:
        try:
            bp = await client.get_blueprint(blueprint)
            if bp is not None:
                migration_id = await client.delete_blueprint(
                    identifier=blueprint, delete_entities=True
                )
                if migration_id:
                    await client.wait_for_migration_to_complete(
                        migration_id=migration_id
                    )
        except Exception as bp_e:
            logger.info(f"Skipping missing blueprint ({blueprint}): {bp_e}")
    headers = await client.auth.headers()
    try:
        await client.client.delete(
            f"{client.auth.api_url}/integrations/{client.integration_identifier}",
            headers=headers,
        )
    except Exception as int_e:
        logger.info(
            f"Failed to delete integration ({client.integration_identifier}): {int_e}"
        )
