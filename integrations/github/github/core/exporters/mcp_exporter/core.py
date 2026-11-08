from typing import Any, Dict, List

from loguru import logger

from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.mcp_exporter.utils import (
    build_mcp_raw_item,
    iter_mcp_servers,
)
from github.core.options import ListFileSearchOptions


class McpExporter(RestFileExporter):
    """Discovers mcp.json/.mcp.json files and emits one entity per MCP server."""

    def _transform_batch(
        self, files: List[Dict[str, Any]], options: List[ListFileSearchOptions]
    ) -> List[Dict[str, Any]]:
        servers: List[Dict[str, Any]] = []
        for file_obj in files:
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
        return servers
