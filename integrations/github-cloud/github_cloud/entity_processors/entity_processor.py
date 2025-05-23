from typing import Any, Optional, Dict, Tuple
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

    def _extract_repo_info(self, data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extract repository path and default branch from data.

        Args:
            data: Entity data

        Returns:
            Tuple of (repo_path, default_branch)

        Raises:
            ValueError: If repository path is missing
        """
        repo_path = data.get("full_name") or data.get("repository", {}).get("full_name")
        if not repo_path:
            logger.error("No repository path found in data")
            raise ValueError("No repository path found in data")

        ref = data.get("default_branch") or data.get("repository", {}).get("default_branch", "main")
        return repo_path, ref

    async def _search(self, data: Dict[str, Any], pattern: str) -> Optional[str]:
        """
        Process a file:// reference.

        Args:
            data: Entity data
            pattern: File reference pattern

        Returns:
            File content

        Raises:
            ValueError: If repository path is missing or pattern is invalid
        """
        try:
            repo_path, ref = self._extract_repo_info(data)
            client = create_github_client()

            if not pattern.startswith(FILE_PROPERTY_PREFIX):
                raise ValueError(f"Invalid file pattern format: {pattern}")

            file_path = pattern[len(FILE_PROPERTY_PREFIX):]
            if not file_path:
                raise ValueError("Empty file path in pattern")

            logger.info(
                f"Fetching content for file: '{file_path}' in repository: '{repo_path}' (branch: '{ref}')"
            )
            return await client.get_file_content(repo_path, file_path, ref)

        except ValueError as e:
            logger.error(f"Invalid file reference: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch file content: {str(e)}")
            raise ValueError(f"Failed to fetch file content: {str(e)}")


class SearchEntityProcessor(JQEntityProcessor):
    """
    Entity processor for search:// references.

    Checks if files matching a search query exist in GitHub Cloud repositories.
    """

    def _extract_repo_info(self, data: Dict[str, Any]) -> str:
        """
        Extract repository path from data.

        Args:
            data: Entity data

        Returns:
            Repository path

        Raises:
            ValueError: If repository path is missing
        """
        repo_path = data.get("full_name") or data.get("repository", {}).get("full_name")
        if not repo_path:
            logger.error("No repository path found in data")
            raise ValueError("No repository path found in data")
        return repo_path

    def _parse_search_pattern(self, pattern: str) -> Tuple[str, Optional[str]]:
        """
        Parse search pattern into path and query components.

        Args:
            pattern: Search reference pattern

        Returns:
            Tuple of (path, query)

        Raises:
            ValueError: If pattern is invalid
        """
        if not pattern.startswith(SEARCH_PROPERTY_PREFIX):
            raise ValueError(f"Invalid search pattern format: {pattern}")

        search_str = pattern[len(SEARCH_PROPERTY_PREFIX):].strip()
        search_parts = search_str.split("&&")

        path = None
        query = None

        for part in search_parts:
            part = part.strip()
            if part.startswith("path="):
                path = part[len("path="):].strip()
            elif part.startswith("query="):
                query = part[len("query="):].strip()

        if not path:
            raise ValueError("Search string must include a 'path=' component")

        return path, query

    async def _search(self, data: Dict[str, Any], pattern: str) -> bool:
        """
        Process a search:// reference.

        Args:
            data: Entity data
            pattern: Search reference pattern

        Returns:
            Boolean indicating if matching files exist

        Raises:
            ValueError: If repository path is missing or pattern is invalid
        """
        try:
            repo_path = self._extract_repo_info(data)
            path, query = self._parse_search_pattern(pattern)
            client = create_github_client()

            logger.info(
                f"Checking for file existence in: '{repo_path}', path: '{path}', query: '{query}'"
            )
            return await client.file_exists(repo_path, path)

        except ValueError as e:
            logger.error(f"Invalid search reference: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to check file existence: {str(e)}")
            raise ValueError(f"Failed to check file existence: {str(e)}")
