from typing import Any, Union, cast
from braceexpand import braceexpand  

import json
import yaml
from loguru import logger


def convert_glob_to_gitlab_patterns(pattern: Union[str, list[str]]) -> list[str]:
    """Converts glob patterns into GitLab-compatible patterns."""
    if isinstance(pattern, list):
        expanded_patterns: list[str] = []
        for glob_pattern in pattern:
            # Cast the result to help mypy understand the return type
            expanded_patterns.extend(cast(list[str], braceexpand(glob_pattern)))
        return expanded_patterns

    # Handle case where the input is a single pattern
    return list(cast(list[str], braceexpand(pattern)))


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
