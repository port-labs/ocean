"""
Module for file processing functions used by the Azure DevOps client.
Handles pattern matching, content parsing, and file processing.
"""

from enum import StrEnum
import json
import re
from typing import Any, Dict, List, NamedTuple, Optional, Union
from loguru import logger
import yaml
from braceexpand import braceexpand
import fnmatch
from wcmatch import glob


class RecursionLevel(StrEnum):
    NONE = "none"
    ONE_LEVEL = "oneLevel"
    FULL = "full"


class PathDescriptor(NamedTuple):
    base_path: str
    recursion: RecursionLevel
    pattern: str


RECURSION_PRIORITY = {
    RecursionLevel.NONE: 0,
    RecursionLevel.ONE_LEVEL: 1,
    RecursionLevel.FULL: 2,
}


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


def is_glob_pattern(pattern: str) -> bool:
    glob_chars = r"(?<!\\)([*?\[\]{}!@+])"
    return bool(re.search(glob_chars, pattern))


def get_priority(recursion: RecursionLevel) -> int:
    return RECURSION_PRIORITY.get(recursion, 0)


def extract_descriptor_from_pattern(pattern: str) -> PathDescriptor:
    """
    For a given path or glob pattern, return:
    - the static base path (before any glob)
    - the appropriate Azure DevOps recursion level
    - the original pattern
    """
    normalized = pattern.strip("/")
    parts = normalized.split("/")

    base_parts = []
    recursion = RecursionLevel.NONE

    for part in parts:
        if is_glob_pattern(part):
            globstar_pattern = r"(?<!\\)\*\*(?![\*\\])"
            if bool(re.search(globstar_pattern, pattern)):
                recursion = RecursionLevel.FULL
            else:
                recursion = RecursionLevel.ONE_LEVEL
            break
        base_parts.append(part)

    base_path = "/" + "/".join(base_parts) if base_parts else "/"
    return PathDescriptor(base_path=base_path, recursion=recursion, pattern=pattern)


def group_descriptors_by_base(
    descriptors: List[PathDescriptor],
) -> Dict[str, List[PathDescriptor]]:
    """
    Group multiple PathDescriptors by their base_path.
    """
    grouped: Dict[str, List[PathDescriptor]] = {}
    for desc in descriptors:
        grouped.setdefault(desc.base_path, []).append(desc)
    return grouped


def separate_glob_and_literal_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Separate a list of paths into (literal_paths, glob_patterns)."""
    literals, globs = [], []

    for p in paths:
        if is_glob_pattern(p):
            globs.append(p)
        else:
            literals.append(p)
    return literals, globs


def matches_glob_pattern(path: str, pattern: str) -> bool:
    """
    Returns True if the path matches the given glob pattern.
    Supports ** and other extended glob syntax via wcmatch.
    """
    return glob.globmatch(
        path.strip("/"), pattern.strip("/"), flags=glob.GLOBSTAR | glob.IGNORECASE
    )


def filter_files_by_glob(
    files: list[dict[str, Any]], pattern: PathDescriptor
) -> list[dict[str, Any]]:
    """
    Return only the files that match the given PathDescriptor pattern.
    Skips folders.
    """
    matched = []

    for file in files:
        if file.get("isFolder", False):
            continue

        path = file["path"].lstrip("/")
        if matches_glob_pattern(path, pattern.pattern):
            matched.append(file)

    return matched
