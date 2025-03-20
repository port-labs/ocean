from typing import Any, Union, cast
from braceexpand import braceexpand

import json
import yaml
from loguru import logger


def strip_recursive_prefix(pattern: str) -> str:
    return pattern[3:] if pattern.startswith("**/") else pattern


def convert_glob_to_gitlab_patterns(pattern: Union[str, list[str]]) -> list[str]:
    """Converts glob patterns into GitLab-compatible patterns."""
    if isinstance(pattern, list):
        expanded_patterns: list[str] = []
        for glob_pattern in pattern:
            stripped_pattern = strip_recursive_prefix(glob_pattern)
            expanded_patterns.extend(braceexpand(stripped_pattern))
        return expanded_patterns

    # Handle single pattern
    stripped_pattern = strip_recursive_prefix(pattern)
    return list(braceexpand(stripped_pattern))


def parse_file_content(
    content: str, file_path: str = "unknown", context: str = "unknown"
) -> Union[str, dict[str, Any], list[Any]]:
    """Parse file content as JSON or YAML, falling back to raw string if parsing fails."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            logger.debug(f"Trying to parse file {file_path} in {context} as YAML")
            documents = list(yaml.load_all(content, Loader=yaml.SafeLoader))
            if not documents:
                logger.debug(
                    f"Failed to parse {file_path} as YAML, returning raw content"
                )
                return content
            return documents if len(documents) > 1 else documents[0]
        except yaml.YAMLError:
            logger.debug(
                f"Failed to parse {file_path} as JSON/YAML, returning raw content"
            )
            return content
