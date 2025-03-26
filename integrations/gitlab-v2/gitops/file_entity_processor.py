from typing import Any, Dict

from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor

from clients.client_factory import create_gitlab_client

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"


class GitLabFileProcessor(JQEntityProcessor):
    """
    Custom entity processor that handles file:// references for GitLab files.
    """

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """Handle file:// and search:// patterns in search."""
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            file_path = pattern.replace(FILE_PROPERTY_PREFIX, "")
            logger.debug(f"Processing file reference: {file_path}")

            client = create_gitlab_client()
            project_id = data["path_with_namespace"]
            ref = data["default_branch"]
            return await client.get_file_content(project_id, file_path, ref)

        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            search_str = pattern.replace(SEARCH_PROPERTY_PREFIX, "").strip()
            logger.debug(f"Processing search reference: {search_str}")

            parts = search_str.split("&&")

            scope_part, query_part = map(str.strip, parts)

            scope = scope_part[len("scope=") :].strip()
            query = query_part[len("query=") :].strip()

            logger.debug(f"Parsed scope: {scope}, query: {query}")

            client = create_gitlab_client()
            project_id = data["path_with_namespace"]
            return await client.file_exists(project_id, scope, query)

        # Fall back to default behavior for other patterns
        return await super()._search(data, pattern)
