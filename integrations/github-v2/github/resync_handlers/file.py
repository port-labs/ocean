from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from github.exporters.file import FileExporter


@ocean.on_resync("file")
async def resync_files(kind: str) -> list[dict[str, Any]]:
    logger.info(f"🔄 Starting file resync for kind: {kind}")
    try:
        exporter = FileExporter(repo="demo-repo", path="")
        files = await exporter.export()
        logger.info("✅ File resync completed successfully")
        return files
    except Exception as e:
        logger.error(f"❌ Error during file resync: {str(e)}", exc_info=True)
        raise


