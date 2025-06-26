import base64
import binascii
from collections import defaultdict
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, TypedDict, TYPE_CHECKING

import yaml
from loguru import logger
from wcmatch import glob

from github.core.options import FileSearchOptions, ListFileSearchOptions
from github.helpers.utils import GithubClientType

if TYPE_CHECKING:
    from integration import GithubFilePattern

JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")
MAX_FILE_SIZE = 1024 * 1024  # 1MB limit in bytes
GRAPHQL_MAX_FILE_SIZE = 100_000
FIELD_NAME_PATTERN = re.compile(r"^f(\d+)$")


class FileObject(TypedDict):
    """Structure for processed file data."""

    content: Any
    repository: Dict[str, Any]
    branch: str
    metadata: Dict[str, Any]


def decode_content(content: str, encoding: str) -> str:
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
        if file_path.endswith(JSON_FILE_SUFFIX) or file_path.endswith(YAML_FILE_SUFFIX):
            return yaml.safe_load(content)
        else:
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


def build_repo_path_map(
    files: List["GithubFilePattern"],
) -> List[ListFileSearchOptions]:
    repo_map: Dict[str, List[FileSearchOptions]] = defaultdict(list)

    for file_selector in files:
        path = file_selector.path
        skip_parsing = file_selector.skip_parsing
        repo_branch_mappings = file_selector.repos

        for repo_branch_mapping in repo_branch_mappings:
            repo = repo_branch_mapping.repo
            branch = repo_branch_mapping.branch

            repo_map[repo].append(
                {
                    "path": path,
                    "skip_parsing": skip_parsing,
                    "branch": branch,
                }
            )

    return [
        ListFileSearchOptions(repo_name=repo, files=files)
        for repo, files in repo_map.items()
    ]


def match_file_entry(path: str, pattern: str) -> bool:
    """
    Match file path against a glob pattern using wcmatch's globmatch.
    Supports ** and other extended glob syntax.
    """
    return glob.globmatch(path, pattern, flags=glob.GLOBSTAR)


def classify_fetch_method(size: int) -> GithubClientType:
    return (
        GithubClientType.GRAPHQL
        if size <= GRAPHQL_MAX_FILE_SIZE
        else GithubClientType.REST
    )


def match_files(tree: List[Dict[str, Any]], pattern: str) -> List[Dict[str, Any]]:
    """Filter GitHub tree blobs by type and size."""

    matched_files = []

    for entry in tree:
        type_ = entry["type"]
        path = entry["path"]
        size = entry.get("size", 0)

        if (
            type_ == "blob"
            and size <= MAX_FILE_SIZE
            and match_file_entry(path, pattern)
        ):
            fetch_method = classify_fetch_method(size)
            matched_files.append(
                {
                    "path": path,
                    "fetch_method": fetch_method,
                }
            )

    return matched_files


def get_graphql_file_metadata(
    host: str, organization: str, repo_name: str, branch: str, file_path: str, size: int
) -> Dict[str, Any]:
    """
    Get metadata for a file from the GraphQL API.
    """
    url = f"{host}/repos/{organization}/{repo_name}/contents/{file_path}?ref={branch}"
    name = file_path.split("/")[-1]

    return {
        "url": url,
        "name": name,
        "path": file_path,
        "size": size,
    }


def build_batch_file_query(
    repo_name: str, owner: str, branch: str, file_paths: List[str]
) -> Dict[str, Any]:
    """
    Build a GraphQL query to fetch multiple files from a repository.
    """
    objects = "\n".join(
        f"""
        f{i}: object(expression: "{branch}:{path}") {{
            ... on Blob {{
                text
                byteSize
            }}
        }}
        """
        for i, path in enumerate(file_paths)
    )

    query = f"""
    query {{
      repository(owner: "{owner}", name: "{repo_name}") {{
        {objects}
      }}
    }}
    """
    return {"query": query}


def get_matching_files(
    files_to_process: List[Dict[str, Any]], matching_patterns: List["GithubFilePattern"]
) -> List[Dict[str, Any]]:
    matching_files = []
    for file_info in files_to_process:
        file_path = file_info["filename"]
        matched_patterns = []

        for pattern in matching_patterns:
            if match_file_entry(file_path, pattern.path):
                matched_patterns.append(pattern)

        if matched_patterns:
            file_info["patterns"] = matched_patterns
            matching_files.append(file_info)

    return matching_files


def extract_file_index(field_name: str) -> Optional[int]:
    match = FIELD_NAME_PATTERN.match(field_name)
    if match:
        return int(match.group(1))
    return None
