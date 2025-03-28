import json
from typing import Any, Dict, Type, Optional
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from bitbucket_cloud.client import BitbucketClient

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _get_file_content(
        self, client: BitbucketClient, repo_slug: str, ref: str, file_path: str
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""
        try:
            file_content = await client.get_repository_files(repo_slug, ref, file_path)
            return (
                json.loads(file_content)
                if file_path.endswith(JSON_SUFFIX)
                else file_content
            )
        except Exception as e:
            logger.error(f"Failed to get file content for {file_path}: {e}")
            return None

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """Search for a file in the repository and return its content."""
        client = BitbucketClient.create_from_ocean_config()
        repo_data = data.get("repo", data)
        repo_slug = repo_data.get("name", "")
        default_branch = repo_data.get("mainbranch", {}).get("name", "main")

        if current_directory_path := data.get("folder", {}).get("path", ""):
            file_path = f"{current_directory_path}/{pattern.replace(self.prefix, '')}"
            ref = data.get("folder", {}).get("commit", {}).get("hash", default_branch)
        else:
            file_path = pattern.replace(self.prefix, "")
            if not default_branch:
                logger.info(f"No default branch found for repository {repo_slug}")
                return None
            ref = default_branch

        if not repo_slug:
            logger.info("No repository slug found")
            return None

        logger.info(
            f"Searching for file {file_path} in Repository {repo_slug}, ref {ref}"
        )
        return await self._get_file_content(client, repo_slug, ref, file_path)


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)
