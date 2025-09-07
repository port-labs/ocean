from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from github.exporters.issue import IssueExporter


@ocean.on_resync("issue")
async def resync_issues(kind: str) -> list[dict[str, Any]]:
    logger.info(f"🔄 Starting issue resync for kind: {kind}")
    try:
        exporter = IssueExporter(repo="demo-repo")
        issues = await exporter.export()
        logger.info("✅ Issue resync completed successfully")
        return issues
    except Exception as e:
        logger.error(f"❌ Error during issue resync: {str(e)}", exc_info=True)
        raise


