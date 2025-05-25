from enum import StrEnum
from loguru import logger
from typing import Any, Union
import json
import yaml


class ObjectKind(StrEnum):
    """Kinds of GitHub objects supported by the integration."""
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    TEAM = "team"
    USER = "user"
    ISSUE = "issue"
    WORKFLOW = "workflow"


def parse_file_content(
    content: str,
    file_path: str,
    context: str,
) -> Union[str, dict[str, Any], list[Any]]:
    """
    Parse file content as JSON or YAML.

    Args:
        content: File content
        file_path: Path to file
        context: Context for logging

    Returns:
        Parsed content or original string if parsing fails
    """
    if not content.strip():
        logger.debug(
            f"File '{file_path}' in '{context}' is empty; returning raw content."
        )
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass  # Proceed to try YAML

    # Try YAML
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
