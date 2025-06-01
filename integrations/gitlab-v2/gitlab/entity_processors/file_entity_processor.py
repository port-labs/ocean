from typing import Any, Optional
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from gitlab.clients.client_factory import create_gitlab_client

FILE_PROPERTY_PREFIX = "file://"


class FileEntityProcessor(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Optional[str]:
        project_id = data.get("path_with_namespace") or data.get("repo", {}).get(
            "path_with_namespace"
        )
        if not project_id:
            logger.error("No project path found in data")
            raise ValueError("No project path found in data")

        ref = data.get("default_branch") or data.get("repo", {}).get("default_branch")
        if not ref:
            logger.error("No branch reference found in data")
            raise ValueError("No branch reference found in data")

        client = create_gitlab_client()
        file_path = pattern[len(FILE_PROPERTY_PREFIX) :]

        logger.info(
            f"Fetching content for file: '{file_path}' in project: '{project_id}' (branch: '{ref}')"
        )
        return await client.get_file_content(project_id, file_path, ref)
