from enum import Enum
from loguru import logger
from typing import Any, Union, List, Dict, Optional
import json
import yaml


class ObjectKind(str, Enum):
    """
    Enum for different types of GitHub objects.
    """
    REPOSITORY = "repository"
    MEMBER = "member"
    TEAM_WITH_MEMBERS = "team-with-members"
    PULL_REQUEST = "pull-request"
    WORKFLOW_RUN = "workflow-run"
    WORKFLOW_JOB = "workflow-job"
    ISSUE = "issue"


def _try_parse_json(content: str, file_path: str, context: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """
    Try to parse content as JSON.

    Args:
        content: Content to parse
        file_path: Path to file
        context: Context for logging

    Returns:
        Parsed JSON or None if parsing fails
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.debug(f"Failed to parse '{file_path}' in '{context}' as JSON")
        return None


def _try_parse_yaml(content: str, file_path: str, context: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """
    Try to parse content as YAML.

    Args:
        content: Content to parse
        file_path: Path to file
        context: Context for logging

    Returns:
        Parsed YAML or None if parsing fails
    """
    try:
        # Try parsing as multi-document YAML first
        documents = list(yaml.safe_load_all(content))
        if not documents or all(doc is None for doc in documents):
            logger.debug(f"No valid YAML documents found in '{file_path}' (context='{context}')")
            return None
        return documents[0] if len(documents) == 1 else documents
    except yaml.YAMLError:
        try:
            # Try parsing as single-document YAML
            result = yaml.safe_load(content)
            if result is None:
                logger.debug(f"Empty YAML document in '{file_path}' (context='{context}')")
                return None
            return result
        except yaml.YAMLError:
            logger.debug(f"Failed to parse '{file_path}' in '{context}' as YAML")
            return None


def parse_file_content(
    content: str,
    file_path: str,
    context: str,
) -> Union[str, Dict[str, Any], List[Any]]:
    """
    Parse file content as JSON or YAML.

    Args:
        content: File content
        file_path: Path to file
        context: Context for logging

    Returns:
        Parsed content or original string if parsing fails

    Note:
        The function attempts to parse the content as JSON first,
        then as YAML if JSON parsing fails. If both fail, returns
        the original content as a string.
    """
    if not content.strip():
        logger.debug(f"File '{file_path}' in '{context}' is empty; returning raw content")
        return content

    # Try JSON first
    if json_result := _try_parse_json(content, file_path, context):
        return json_result

    # Try YAML if JSON fails
    if yaml_result := _try_parse_yaml(content, file_path, context):
        return yaml_result

    # Return original content if both parsing attempts fail
    logger.debug(
        f"Failed to parse file '{file_path}' in '{context}' as JSON or YAML. "
        "Returning raw content"
    )
    return content
