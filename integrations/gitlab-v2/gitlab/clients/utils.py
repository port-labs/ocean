import json
from typing import Any, Union

import yaml
from loguru import logger


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
