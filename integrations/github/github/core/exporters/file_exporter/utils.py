import binascii
import json
import os
from typing import Dict, List, Any, Optional, Tuple, TypedDict
from pathlib import Path
import base64

import yaml
from loguru import logger


JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")


class FileObject(TypedDict):
    """Structure for processed file data."""

    content: Any
    repository: Dict[str, Any]
    branch: str
    metadata: Dict[str, Any]


def normalize_path(path: str) -> str:
    dir_path = os.path.dirname(path)
    return os.path.normpath(dir_path)


def validate_file_match(full_path: str, filename: str, path: str) -> bool:
    normalized_path = normalize_path(path)
    expected_path = os.path.normpath(os.path.join(normalized_path, filename))

    return full_path == expected_path


def build_search_query(
    filename: str, path: str, organization: str, repos: Optional[List[str]] = None
) -> str:
    """

    Args:
        filenames: List of filenames to search for (e.g., ["README.md", "config.yaml"]).
        path: Directory path to search in (e.g., "src/").
        repos: Optional list of repository names in "owner/repo" format.

    Returns:
        A formatted search query string.
    """

    search_terms = [f"filename:{filename}"]

    if repos:
        search_terms.append(" ".join(f"repo:{organization}/{repo}" for repo in repos))
    else:
        search_terms.append(f"org:{organization}")

    normalized_path = normalize_path(path)
    search_terms.append(f"path:/{normalized_path}")

    return " ".join(search_terms)


def decode_content(content: str, encoding: Optional[str] = None) -> str:
    """
    Parse the content of a file.

    Args:
        content: The content to parse
        encoding: The encoding of the content, currently only supports 'base64'

    Returns:
        str: The decoded content

    Raises:
        binascii.Error: If base64 decoding fails
        UnicodeDecodeError: If UTF-8 decoding fails
        ValueError: If an unsupported encoding is provided
    """

    if encoding != "base64":
        raise ValueError(f"Unsupported encoding: {encoding}")

    try:
        return base64.b64decode(content).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as e:
        logger.error(f"Failed to decode content: {str(e)}")
        raise


def parse_content(content: str, file_path: str) -> Any:
    """Parse a file based on its extension."""
    try:
        if file_path.endswith(JSON_FILE_SUFFIX):
            loaded_file = json.loads(content)
            content = loaded_file
        elif file_path.endswith(YAML_FILE_SUFFIX):
            loaded_file = yaml.safe_load(content)
            content = loaded_file
        return content
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        return content


def group_files_by_status(
    files: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    deleted_files: List[Dict[str, Any]] = []
    updated_files: List[Dict[str, Any]] = []

    for file in files:
        (deleted_files if file.get("status") == "removed" else updated_files).append(
            file
        )

    return deleted_files, updated_files


def is_matching_file(files: List[Dict[str, Any]], filenames: List[str]) -> bool:
    """Check if any file in diff_stat_files matches the specified filenames."""
    filenames_set = set(filenames)
    return any(Path(file_info["filename"]).name in filenames_set for file_info in files)
