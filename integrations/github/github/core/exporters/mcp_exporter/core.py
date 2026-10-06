from typing import Any, List

from loguru import logger

from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.mcp_exporter.utils import (
    build_mcp_raw_item,
    iter_mcp_servers,
)
from github.core.options import ListFileSearchOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class McpExporter(RestFileExporter):
    """Discovers mcp.json/.mcp.json files and emits one entity per MCP server."""

    async def get_paginated_resources[ExporterOptionsT: List[ListFileSearchOptions]](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for file_batch in super().get_paginated_resources(options):
            servers: list[dict[str, Any]] = []
            for file_obj in file_batch:
                content = file_obj.get("content")
                if not isinstance(content, dict):
                    logger.warning(
                        f"Skipping mcp file {file_obj.get('path')} — "
                        "content is not a JSON object"
                    )
                    continue
                for name, server_config in iter_mcp_servers(content):
                    servers.append(
                        build_mcp_raw_item(
                            file_path=file_obj["path"],
                            server_name=name,
                            server_config=server_config,
                            repository=file_obj["repository"],
                            branch=file_obj["branch"],
                            organization=file_obj.get("organization"),
                            blob_sha=file_obj.get("metadata", {}).get("sha"),
                        )
                    )
            if servers:
                yield servers
