from typing import Any, Dict, Optional
from port_ocean.core.handlers import JQEntityProcessor
from loguru import logger
from helpers.client_factory import create_gitlab_client


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

        client = create_gitlab_client()
        project_id = data["path_with_namespace"]

        ref = data["default_branch"]
        return await client.get_file_content(project_id, file_path, ref)
