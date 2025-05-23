from typing import Any, Optional, Dict
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from github_cloud.clients.client_factory import create_github_client

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"


class FileEntityProcessor(JQEntityProcessor):
    """
    Entity processor for file:// references.

    Fetches file content from GitHub Cloud repositories.
    """

    async def _search(self, data: dict[str, Any], pattern: str) -> Optional[str]:
        """
        Process a file:// reference.

        Args:
            data: Entity data
            pattern: File reference pattern

        Returns:
            File content
        """
        repo_path = data.get("full_name") or data.get("repository", {}).get("full_name")
        if not repo_path:
            logger.error("No repository path found in data")
            raise ValueError("No repository path found in data")

        ref = data.get("default_branch") or data.get("repository", {}).get("default_branch", "main")

        client = create_github_client()
        file_path = pattern[len(FILE_PROPERTY_PREFIX):]

        logger.info(
            f"Fetching content for file: '{file_path}' in repository: '{repo_path}' (branch: '{ref}')"
        )
        return await client.get_file_content(repo_path, file_path, ref)


class SearchEntityProcessor(JQEntityProcessor):
    """
    Entity processor for search:// references.

    Checks if files matching a search query exist in GitHub Cloud repositories.
    """

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """
        Process a search:// reference.

        Args:
            data: Entity data
            pattern: Search reference pattern

        Returns:
            Boolean indicating if matching files exist
        """
        client = create_github_client()
        repo_path = data.get("full_name") or data.get("repository", {}).get("full_name")

        if not repo_path:
            logger.error("No repository path found in data")
            raise ValueError("No repository path found in data")

        search_str = pattern[len(SEARCH_PROPERTY_PREFIX):].strip()
        search_parts = search_str.split("&&")

        path = None
        query = ""

        for part in search_parts:
            part = part.strip()
            if part.startswith("path="):
                path = part[len("path="):].strip()
            elif part.startswith("query="):
                query = part[len("query="):].strip()

        if not path:
            logger.error(f"Invalid search string format (missing path): {search_str}")
            raise ValueError("Search string must include a 'path=' component")

        logger.info(
            f"Checking for file existence in: '{repo_path}', path: '{path}', query: '{query}'"
        )
        return await client.file_exists(repo_path, path)
