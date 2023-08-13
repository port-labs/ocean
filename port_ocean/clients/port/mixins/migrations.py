import asyncio
from urllib.parse import quote_plus

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_status_code
from port_ocean.core.models import Migration


class MigrationClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client

    async def wait_for_migration_to_complete(
        self,
        migration_id: list[str],
        interval: int = 5,
    ) -> Migration:
        logger.info(
            f"Waiting for migration with id: {migration_id} to complete",
        )

        headers = await self.auth.headers()
        response = await self.client.get(
            f"{self.auth.api_url}/migrations/{migration_id}",
            headers=headers,
        )

        if response.is_error:
            logger.error(
                f"Could not get migration status with id: {migration_id}. Error: {response.text}"
            )

        handle_status_code(response, should_raise=True)

        migration_status = response.json().get("migration", {}).get("status", None)
        if (
            migration_status == "RUNNING"
            or migration_status == "INITIALIZING"
            or migration_status == "PENDING"
        ):
            await asyncio.sleep(interval)
            await self.wait_for_migration_to_complete(migration_id, interval)

        logger.info(
            f"Migration with id: {migration_id} completed successfully",
        )

        return Migration.parse_obj(response.json()["migration"])
