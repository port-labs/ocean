from typing import Any
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from gitlab.clients.client_factory import create_gitlab_client

FILE_PROPERTY_PREFIX = "file://"


class FileEntityProcessor(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        project_id = data["path_with_namespace"]
        ref = data["default_branch"]
        client = create_gitlab_client()
        file_path = pattern[len(FILE_PROPERTY_PREFIX) :]

        logger.info(
            f"Fetching content for file: '{file_path}' in project: '{project_id}' (branch: '{ref}')"
        )
        return await client.get_file_content(project_id, file_path, ref)
