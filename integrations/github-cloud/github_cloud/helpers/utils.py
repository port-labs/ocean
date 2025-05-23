from enum import StrEnum
from loguru import logger
from typing import Any, Union
import json
import yaml


class ObjectKind(StrEnum):
    """Kinds of GitHub Cloud objects supported by the integration."""
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    TEAM_WITH_MEMBERS = "team-with-members"
    MEMBER = "member"
    WORKFLOW_RUN = "workflow-run"
    WORKFLOW_JOB = "workflow-job"


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
        pass

    logger.debug(f"Attempting to parse file '{file_path}' in '{context}' as YAML.")
    try:
        try:
            documents = list(yaml.safe_load_all(content))
            if not documents or all(doc is None for doc in documents):
                logger.debug(
                    f"No valid YAML documents found in file '{file_path}' (context='{context}')."
                    " Returning raw content."
                )
                return content
            return documents[0] if len(documents) == 1 else documents
        except yaml.YAMLError:
            try:
                result = yaml.safe_load(content)
                if result is None:
                    logger.debug(
                        f"Empty YAML document in file '{file_path}' (context='{context}')."
                        " Returning raw content."
                    )
                    return content
                return result
            except yaml.YAMLError:
                logger.debug(
                    f"Failed to parse file '{file_path}' in '{context}' as JSON or YAML. "
                    "Returning raw content."
                )
                return content
    except Exception as e:
        logger.debug(
            f"Unexpected error parsing file '{file_path}' in '{context}': {str(e)}. "
            "Returning raw content."
        )
        return content
