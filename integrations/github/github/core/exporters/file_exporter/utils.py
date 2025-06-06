import binascii
import json
from typing import Dict, List, Any, Optional, TypedDict
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

    normalized_path = path.lstrip("/").rstrip("*")
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


def find_deleted_files(files: List[Dict[str, Any]]) -> list[dict[str, Any]]:
    return [file for file in files if file["status"] == "removed"]


def is_matching_file(files: List[Dict[str, Any]], filenames: List[str]) -> bool:
    """Check if any file in diff_stat_files matches the specified filenames."""
    filenames_set = set(filenames)
    return any(Path(file_info["filename"]).name in filenames_set for file_info in files)
