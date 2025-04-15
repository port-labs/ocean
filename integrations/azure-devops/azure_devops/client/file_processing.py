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


def match_pattern(pattern: Union[str, List[str]], string: str) -> bool:
    """
    Check if a string matches a pattern or list of patterns.
    Matches GitLab's implementation for consistency.
    """
    try:
        string = string.lstrip("/")
        if isinstance(pattern, list):
            return any(match_pattern(p, string) for p in pattern)
        return fnmatch.fnmatch(string, pattern)
    except Exception as e:
        logger.error(f"Error in pattern matching: {str(e)}")
        return False


def expand_patterns(pattern: Union[str, List[str]]) -> List[str]:
    """Convert glob patterns with brace expansion into a list of patterns."""
    if isinstance(pattern, list):
        return [p for glob_pattern in pattern for p in braceexpand(glob_pattern)]
    return list(braceexpand(pattern))


def get_base_paths(patterns: List[str]) -> List[str]:
    """Extract base paths from glob patterns to minimize API requests."""
    base_paths = set()
    for pattern in patterns:
        if pattern.startswith("**"):
            base_paths.add("**")
            continue

        parts = pattern.split("/")
        if any("*" in part or "?" in part for part in parts[:-1]):
            base_paths.add("/")
            continue

        base_path = "/".join(p for p in parts if "*" not in p and "?" not in p)
        base_paths.add(base_path if base_path else "/")

    return list(base_paths)


async def parse_file_content(content: bytes) -> Union[dict[str, Any], list[Any], str]:
    """
    Parse file content based on file type. Matches GitLab's implementation.
    """
    if not content:
        return ""

    content_str = content.decode("utf-8")

    # Try JSON first
    try:
        return json.loads(content_str)
    except json.JSONDecodeError:
        # Then try YAML
        try:
            # Handle multi-document YAML files
            if content_str.startswith("---"):
                docs = list(yaml.safe_load_all(content_str))
                docs = [doc for doc in docs if doc is not None]
                if len(docs) > 1:
                    return docs
                elif len(docs) == 1:
                    return docs[0]
                return content_str

            result = yaml.safe_load(content_str)
            if result is None:
                return content_str
            return result
        except yaml.YAMLError:
            return content_str


async def generate_file_object_from_repository_file(
    file_metadata: dict[str, Any],
    file_content: bytes,
    repository_metadata: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Process a file's content and create a file object."""
    try:
        parsed_content = await parse_file_content(file_content)
        return {
            "file": {
                **file_metadata,
                "content": {
                    "raw": file_content.decode("utf-8"),
                    "parsed": parsed_content,
                },
                "size": len(file_content),
            },
            "repo": repository_metadata,
        }
    except Exception as e:
        logger.error(
            f"Failed to process file {file_metadata.get('path', 'unknown')}: {str(e)}"
        )
        return None
