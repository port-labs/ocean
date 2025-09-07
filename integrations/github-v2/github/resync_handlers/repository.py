from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from github.exporters.respository import RepositoryExporter


@ocean.on_resync("repository")
async def resync_repositories(kind: str) -> list[dict[str, Any]]:
    logger.info(f"🔄 Starting repository resync for kind: {kind}")
    try:
        exporter = RepositoryExporter()
        repos = await exporter.export()
        logger.info("✅ Repository resync completed successfully")
        return repos
    except Exception as e:
        logger.error(f"❌ Error during repository resync: {str(e)}", exc_info=True)
        raise


