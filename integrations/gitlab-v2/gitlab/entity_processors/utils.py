from loguru import logger
from typing import Tuple, Any, Union
import json

import yaml


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


def parse_file_content(
    content: str,
    file_path: str = "unknown",
    context: str = "unknown",
) -> Union[str, dict[str, Any], list[Any]]:
    """
    Attempt to parse a string as JSON or YAML. If both parse attempts fail or the content
    is empty, the function returns the original string.

    :param content:    The raw file content to parse.
    :param file_path:  Optional file path for logging purposes (default: 'unknown').
    :param context:    Optional contextual info for logging purposes (default: 'unknown').
    :return:           A dictionary or list (if parsing was successful),
                       or the original string if parsing fails.
    """
    # Quick check for empty or whitespace-only strings
    if not content.strip():
        logger.debug(
            f"File '{file_path}' in '{context}' is empty; returning raw content."
        )
        return content

    # 1) Try JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass  # Proceed to try YAML

    # 2) Try YAML
    logger.debug(f"Attempting to parse file '{file_path}' in '{context}' as YAML.")
    try:
        documents = list(yaml.load_all(content, Loader=yaml.SafeLoader))
        if not documents:
            logger.debug(
                f"No valid YAML documents found in file '{file_path}' (context='{context}')."
                " Returning raw content."
            )
            return content
        return documents[0] if len(documents) == 1 else documents
    except yaml.YAMLError:
        logger.debug(
            f"Failed to parse file '{file_path}' in '{context}' as JSON or YAML. "
            "Returning raw content."
        )
        return content
