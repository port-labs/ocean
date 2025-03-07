from typing import Any, Dict, Type
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from client import BitbucketClient

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        repo_slug = data.get("name", "")
        default_branch = data.get("mainbranch", {}).get("name", "master")
        client = BitbucketClient.create_from_ocean_config()

        file_path = pattern.replace(self.prefix, "")
        if not repo_slug:
            return None

        logger.info(
            f"Searching for file {file_path} in Repository {repo_slug}, ref {default_branch}"
        )
        try:
            file_content = await client.get_file_content(
                repo_slug, default_branch, file_path
            )
            if file_path.endswith(JSON_SUFFIX):
                import json

                return json.loads(file_content)
            return file_content
        except Exception as e:
            logger.error(f"Failed to get file content for {file_path}: {e}")
            return None


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)
