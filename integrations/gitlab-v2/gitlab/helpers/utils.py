from enum import StrEnum
from loguru import logger
from typing import Any, Union
import json
import yaml


class ObjectKind(StrEnum):
    PROJECT = "project"
    GROUP = "group"
    ISSUE = "issue"
    MERGE_REQUEST = "merge-request"
    GROUP_WITH_MEMBERS = "group-with-members"
    MEMBER = "member"
    FILE = "file"
    PIPELINE = "pipeline"
    JOB = "job"
    FOLDER = "folder"


def parse_file_content(
    content: str,
    file_path: str,
    context: str,
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
