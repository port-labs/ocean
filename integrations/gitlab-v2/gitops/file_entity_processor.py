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

        logger.info(
            f"File {file_path} not found in GraphQL response, No File Found"
        )
        # return await self._fetch_file_rest(data, file_path)

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

    # async def _fetch_file_rest(
    #     self, data: Dict[str, Any], file_path: str
    # ) -> Optional[str]:
    #     """Fall back to fetching file content via REST."""
    #     from main import create_gitlab_client

    #     try:
    #         client = create_gitlab_client()
    #         project_id_raw = data.get("id") or data.get("fullPath")
    #         if project_id_raw is None:
    #             logger.error("No project ID or fullPath found in data")
    #             return None
    #         project_id = str(project_id_raw)

    #         ref = "main"
    #         if "repository" in data and data["repository"].get("rootRef"):
    #             ref = data["repository"]["rootRef"]

    #         return await client.get_file_content(project_id, file_path, ref)
    #     except Exception as e:
    #         logger.error(f"Error fetching file {file_path}: {str(e)}")
    #         return None
