from typing import Any, Dict
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from gitlab.clients.client_factory import create_gitlab_client
from gitlab.entity_processors.utils import parse_search_string
import asyncio
from aiolimiter import AsyncLimiter

SEARCH_PROPERTY_PREFIX = "search://"
MAX_REQUESTS_PER_SECOND = 2
_rate_limiter = AsyncLimiter(MAX_REQUESTS_PER_SECOND, 1)
_semaphore = asyncio.Semaphore(2)


class SearchEntityProcessor(JQEntityProcessor):
    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        async with _semaphore:
            async with _rate_limiter:
                client = create_gitlab_client()
                project_id = data.get("path_with_namespace") or data.get(
                    "repo", {}
                ).get("path_with_namespace")

                if not project_id:
                    logger.error("No project path found in data")
                    raise ValueError("No project path found in data")

                search_str = pattern[len(SEARCH_PROPERTY_PREFIX) :].strip()
                scope, query = parse_search_string(search_str)

                logger.info(
                    f"Checking for file existence using query: '{query}' in scope: '{scope}' for project: '{project_id}'"
                )
                return await client.file_exists(project_id, scope, query)
