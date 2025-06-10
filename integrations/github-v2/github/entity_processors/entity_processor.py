from typing import Any, Optional, Dict
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from github.clients.client_factory import create_github_client

# Property prefixes
FILE_PROPERTY_PREFIX = "file://"

class FileEntityProcessor(JQEntityProcessor):
    """
    Entity processor for file:// references.

    Fetches file content from GitHub repositories.
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

        try:
            return await client.get_file_content(repo_path, file_path, ref)
        except Exception as exc:
            logger.error(f"Failed to fetch file content for '{file_path}' in '{repo_path}': {exc}")
            return None
