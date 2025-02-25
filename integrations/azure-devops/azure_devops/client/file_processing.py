"""
Module for file processing functions used by the Azure DevOps client.
Handles pattern matching, content parsing, and file processing.
"""

import json
from typing import Any, List, Optional, Union
from loguru import logger
import yaml
from braceexpand import braceexpand
import fnmatch

# Constants
MAX_ALLOWED_FILE_SIZE_IN_BYTES = 10 * 1024 * 1024  # 10MB


def match_pattern(pattern: Union[str, List[str]], string: str) -> bool:
    """
    Check if a string matches a pattern or list of patterns.

    Args:
        pattern: Single glob pattern or list of patterns
        string: String to match against pattern(s)
    """
    try:
        string = string.lstrip("/")

        if isinstance(pattern, list):
            return any(match_pattern(p, string) for p in pattern)

        # Handle brace expansion
        for expanded_pattern in braceexpand(pattern):
            if _match_single_pattern(expanded_pattern, string):
                return True
        return False

    except Exception as e:
        logger.error(f"Error in pattern matching: {str(e)}")
        return False


def _match_single_pattern(pattern: str, string: str) -> bool:
    """Match a single pattern against a string."""
    if pattern.startswith("**"):
        # Try both with and without the **/ prefix
        return fnmatch.fnmatch(string, pattern) or fnmatch.fnmatch(
            string, pattern.replace("**/", "")
        )
    return fnmatch.fnmatch(string, pattern)


def expand_patterns(pattern: Union[str, List[str]]) -> List[str]:
    """Convert glob patterns with brace expansion into a list of patterns."""
    if isinstance(pattern, list):
        return [p for glob_pattern in pattern for p in braceexpand(glob_pattern)]
    return list(braceexpand(pattern))


def get_base_paths(patterns: List[str]) -> List[str]:
    """
    Extract base paths from glob patterns to minimize API requests.

    Args:
        patterns: List of glob patterns
    Returns:
        List of base paths to search
    """
    base_paths = set()
    for pattern in patterns:
        if pattern.startswith("**"):
            base_paths.add("**")
            continue

        parts = pattern.split("/")
        if "*" in parts[0] or "?" in parts[0]:
            base_paths.add("/")
        else:
            base_path = "/".join(p for p in parts if "*" not in p and "?" not in p)
            base_paths.add(base_path if base_path else "/")

    return list(base_paths)


async def process_file_content(
    file: dict[str, Any], content: bytes, repository: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """
    Process a file's content and create a file object.

    Args:
        file: File metadata from Azure DevOps
        content: Raw file content
        repository: Repository metadata
    Returns:
        Processed file object or None if processing fails
    """
    if len(content) > MAX_ALLOWED_FILE_SIZE_IN_BYTES:
        logger.warning(
            f"File {file['path']} exceeds size limit of "
            f"{MAX_ALLOWED_FILE_SIZE_IN_BYTES} bytes"
        )
        return None

    try:
        parsed_content = await parse_content(content)
        return {
            "file": {
                **file,
                "content": {"raw": content.decode("utf-8"), "parsed": parsed_content},
                "size": len(content),
            },
            "repo": repository,
        }
    except Exception as e:
        logger.error(f"Failed to process file {file['path']}: {str(e)}")
        return None


async def parse_content(content: bytes) -> Union[dict[str, Any], list[Any], str]:
    """Parse file content as JSON, YAML, or raw text."""
    try:
        return json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        try:
            documents = list(yaml.safe_load_all(content.decode("utf-8")))
            return documents if len(documents) > 1 else documents[0]
        except yaml.YAMLError:
            return content.decode("utf-8")
