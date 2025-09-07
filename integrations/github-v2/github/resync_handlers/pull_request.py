from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from github.exporters.pull_request import PullRequestExporter


@ocean.on_resync("pull-request")
async def resync_pull_requests(kind: str) -> list[dict[str, Any]]:
    logger.info(f"🔄 Starting pull request resync for kind: {kind}")
    try:
        exporter = PullRequestExporter(repo="demo-repo")
        pull_requests = await exporter.export()
        logger.info("✅ Pull request resync completed successfully")
        return pull_requests
    except Exception as e:
        logger.error(f"❌ Error during pull request resync: {str(e)}", exc_info=True)
        raise


