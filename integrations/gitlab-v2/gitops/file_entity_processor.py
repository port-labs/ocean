from typing import Any, Dict, Optional
from port_ocean.core.handlers import JQEntityProcessor
from loguru import logger

FILE_PROPERTY_PREFIX = "file://"


class GitLabFileProcessor(JQEntityProcessor):
    """
    Custom entity processor that handles file:// references for GitLab files.
    """

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """Handle file:// patterns in search."""
        if not pattern.startswith(FILE_PROPERTY_PREFIX):
            return await super()._search(data, pattern)

        file_path = pattern.replace(FILE_PROPERTY_PREFIX, "")
        logger.debug(f"Processing file reference: {file_path}")

        content = self._get_graphql_file_content(data, file_path)
        if content is not None:
            logger.debug(f"Found content for {file_path} in GraphQL response")
            return content

        logger.info(f"File {file_path} not found in GraphQL response, No File Found")

    def _get_graphql_file_content(
        self, data: Dict[str, Any], file_path: str
    ) -> Optional[str]:
        """Get file content from GraphQL response."""
        if "repository" not in data:
            return None

        repo = data["repository"]
        if "blobs" not in repo or not repo["blobs"].get("nodes"):
            return None

        for node in repo["blobs"]["nodes"]:
            if node.get("path") == file_path and "rawBlob" in node:
                return node["rawBlob"]

        return None
