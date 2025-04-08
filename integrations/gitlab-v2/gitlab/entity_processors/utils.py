from loguru import logger
from typing import Tuple


def parse_search_string(search_str: str) -> Tuple[str, str]:

    if (
        "&&" not in search_str
        or "scope=" not in search_str
        or "query=" not in search_str
    ):
        logger.error(f"Invalid search string format: {search_str}")
        raise ValueError(
            "Search string must follow the 'scope=... && query=...' format"
        )
    scope_part, query_part = map(str.strip, search_str.split("&&", 1))
    if not scope_part.startswith("scope=") or not query_part.startswith("query="):
        logger.error(f"Invalid search string content: {search_str}")
        raise ValueError(
            "Search string must follow the 'scope=... && query=...' format"
        )
    scope = scope_part[len("scope=") :].strip()
    query = query_part[len("query=") :].strip()
    return scope, query
