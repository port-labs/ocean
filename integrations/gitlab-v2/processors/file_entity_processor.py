from aiolimiter import AsyncLimiter
from typing import Any, Dict
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from clients.client_factory import create_gitlab_client
from processors.utils import parse_search_string

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"
MAX_REQUESTS_PER_SECOND = 20


class GitLabFileProcessor(JQEntityProcessor):
    """
    Custom entity processor for GitLab file and search operations.
    """

    _rate_limiter = AsyncLimiter(MAX_REQUESTS_PER_SECOND, 1)

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """Handle file:// and search:// patterns in search."""
        async with self._rate_limiter:

            if pattern.startswith(FILE_PROPERTY_PREFIX):
                project_id = data["path_with_namespace"]
                ref = data["default_branch"]
                client = create_gitlab_client()
                file_path = pattern[len(FILE_PROPERTY_PREFIX) :]
                logger.info(
                    f"Fetching content for file: '{file_path}' in project: '{project_id}' (branch: '{ref}')"
                )
                return await client.get_file_content(project_id, file_path, ref)

            elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
                project_id = data["path_with_namespace"]
                ref = data["default_branch"]
                client = create_gitlab_client()
                search_str = pattern[len(SEARCH_PROPERTY_PREFIX) :].strip()
                scope, query = parse_search_string(search_str)

                logger.info(
                    f"Checking for file existence using query: '{query}' in scope: '{scope}' for project: '{project_id}'"
                )
                return await client.file_exists(project_id, scope, query)

            return await super()._search(data, pattern)
