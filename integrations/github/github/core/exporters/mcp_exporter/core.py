from typing import Any, List

from loguru import logger

from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.mcp_exporter.utils import (
    build_mcp_raw_item,
    iter_mcp_servers,
)
from github.core.options import ListFileSearchOptions
from github.helpers.repository_change import RepositoryChange
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class McpExporter(RestFileExporter):
    """Discovers mcp.json/.mcp.json files and emits one entity per MCP server."""

    async def get_paginated_resources[ExporterOptionsT: List[ListFileSearchOptions]](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for servers in self._export_servers(
            super().get_paginated_resources(options)
        ):
            yield servers

    async def get_paginated_resources_changed_since(
        self, options: List[ListFileSearchOptions], change: RepositoryChange
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for servers in self._export_servers(
            super().get_paginated_resources_changed_since(options, change)
        ):
            yield servers

    async def _export_servers(
        self, file_batches: ASYNC_GENERATOR_RESYNC_TYPE
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Turn each batch of MCP config files into one raw item per server."""
        async for file_batch in file_batches:
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
