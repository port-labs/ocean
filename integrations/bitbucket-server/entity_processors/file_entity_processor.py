from typing import Any, Optional
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from initialize_client import init_client

FILE_PROPERTY_PREFIX = "file://"

class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _get_file_content(
        self, project_key: str, repo_slug: str, file_path: str
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""
        try:
            bitbucket_client = init_client()
            return await bitbucket_client.get_file_content(
                project_key, repo_slug, file_path
            )
        except Exception as e:
            logger.error(
                f"Failed to get file content for {file_path} in {project_key}/{repo_slug}: {e}"
            )
            return None

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        """
        Search for a file in the repository and return its content.
        """
        project_key = data.get("project", {}).get("key", "")
        repo_data = data.get("repo", data)
        repo_slug = repo_data.get("slug", "")

        if not project_key or not repo_slug:
            logger.error("Missing project key or repository slug")
            return None

        file_path = pattern.replace(self.prefix, "")
        return await self._get_file_content(project_key, repo_slug, None, file_path)
