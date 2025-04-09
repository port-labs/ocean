from typing import Any, Dict
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from gitlab.clients.client_factory import create_gitlab_client
from gitlab.entity_processors.utils import parse_search_string

SEARCH_PROPERTY_PREFIX = "search://"


class SearchEntityProcessor(JQEntityProcessor):
    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        project_id = data["path_with_namespace"]
        client = create_gitlab_client()
        search_str = pattern[len(SEARCH_PROPERTY_PREFIX) :].strip()
        scope, query = parse_search_string(search_str)

        logger.info(
            f"Checking for file existence using query: '{query}' in scope: '{scope}' for project: '{project_id}'"
        )
        return await client.file_exists(project_id, scope, query)
