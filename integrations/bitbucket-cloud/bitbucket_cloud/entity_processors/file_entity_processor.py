from typing import Any, Optional
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from initialize_client import init_client


FILE_PROPERTY_PREFIX = "file://"


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _get_file_content(
        self, repo_slug: str, ref: str, file_path: str
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""
        try:
            bitbucket_client = init_client()
            return await bitbucket_client.get_repository_files(
                repo_slug, ref, file_path
            )
        except Exception as e:
            logger.error(
                f"Failed to get file content for {file_path} in repository {repo_slug} in branch {ref}: {e}"
            )
            return None

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        """
        Search for a file in the repository and return its content.

        Args:
            data (dict[str, Any]): The data containing the repository information
            pattern (str): The pattern to search for (e.g. "file://path/to/file.yaml")

            For monorepo, the data should contain a "repo" key and a "folder" key with the repository information.
            For non-monorepo, the data should contain the repository information directly.

        Returns:
            Any: The raw or parsed content of the file
        """

        repo_data = data.get("repo", data)
        repo_slug = repo_data.get("name", "").replace(" ", "-")
        default_branch = (
            repo_data.get("mainbranch", {}).get("name", "main").replace(" ", "-")
        )

        if current_directory_path := data.get("folder", {}).get("path", ""):
            file_path = f"{current_directory_path}/{pattern.replace(self.prefix, '')}"
            ref = data.get("folder", {}).get("commit", {}).get("hash", default_branch)
        else:
            file_path = pattern.replace(self.prefix, "")
            if not default_branch:
                logger.info(
                    f"No default branch found for repository {repo_slug} and file path {file_path}"
                )
                return None
            ref = default_branch

        if not repo_slug:
            logger.info(
                f"No repository slug found for branch {ref} and file path {file_path}"
            )
            return None

        logger.info(
            f"Searching for file {file_path} in Repository {repo_slug}, ref {ref}"
        )
        return await self._get_file_content(repo_slug, ref, file_path)
