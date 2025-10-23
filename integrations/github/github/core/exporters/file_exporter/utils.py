import base64
import binascii
from collections import defaultdict
import json
from pathlib import Path
import re
from typing import (
    Any,
    AsyncGenerator,
    DefaultDict,
    Dict,
    List,
    Optional,
    Tuple,
    TypedDict,
    TYPE_CHECKING,
    Union,
)

import yaml
from loguru import logger
from github.clients.utils import get_mono_repo_organization
from wcmatch import glob

from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import (
    FileSearchOptions,
    ListFileSearchOptions,
    ListRepositoryOptions,
)
from github.helpers.utils import GithubClientType

if TYPE_CHECKING:
    from integration import GithubFilePattern

JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")
MAX_FILE_SIZE = 1024 * 1024  # 1MB limit in bytes
GRAPHQL_MAX_FILE_SIZE = 100_000
FIELD_NAME_PATTERN = re.compile(r"^file_(\d+)$")


class FileObject(TypedDict):
    """Structure for processed file data."""

    organization: str
    content: Any
    repository: Dict[str, Any]
    branch: str
    path: str
    name: str
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
        if file_path.endswith(JSON_FILE_SUFFIX):
            return json.loads(content)
        elif file_path.endswith(YAML_FILE_SUFFIX):
            return yaml.safe_load(content)
    except Exception as e:
        logger.error(f"Error parsing file: {e}")

    return content


def group_files_by_status(
    files: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    deleted_files: List[Dict[str, Any]] = []
    updated_files: List[Dict[str, Any]] = []

    for file in files:
        if file.get("status") == "removed":
            deleted_files.append(file)
        else:
            updated_files.append(file)

    return deleted_files, updated_files


def is_matching_file(files: List[Dict[str, Any]], filenames: List[str]) -> bool:
    """Check if any file in diff_stat_files matches the specified filenames."""
    filenames_set = set(filenames)

    for file_info in files:
        file_name = Path(file_info["filename"]).name
        if file_name in filenames_set:
            return True

    return False


async def group_file_patterns_by_repositories_in_selector(
    files: List["GithubFilePattern"],
    repo_exporter: "AbstractGithubExporter[Any]",
    repo_type: str,
    exclude_archived: bool,
) -> List[ListFileSearchOptions]:
    """
    Group file patterns by repository to enable batch processing.

    Takes a list of file patterns with repository mappings and organizes them
    by repository name for efficient batch file fetching. If no repo is specified, fetch the relevant file for every repository
    """
    logger.info(
        f"Grouping file patterns by repository and organization for batch processing from {len(files)} file patterns."
    )

    repo_map: Dict[str, List[FileSearchOptions]] = defaultdict(list)

    async def _get_repos_and_branches_for_selector(
        selector: "GithubFilePattern", path: str
    ) -> AsyncGenerator[Tuple[str, Optional[str]], None]:
        organization = get_mono_repo_organization(selector.organization)
        if selector.repos is None:
            logger.info(
                f"No repositories specified for file pattern '{path}'. Fetching from '{repo_type}' repositories from {organization}."
            )
            repo_option = ListRepositoryOptions(
                organization=organization,
                type=repo_type,
                exclude_archived=exclude_archived,
            )
            async for repo_batch in repo_exporter.get_paginated_resources(repo_option):
                for repository in repo_batch:
                    yield repository["name"], repository["default_branch"]
        else:
            logger.info(
                f"Fetching file pattern '{path}' from specified repositories from {organization}."
            )
            for repo_branch_mapping in selector.repos:
                yield repo_branch_mapping.name, repo_branch_mapping.branch

    for file_selector in files:
        path = file_selector.path
        skip_parsing = file_selector.skip_parsing
        organization = get_mono_repo_organization(file_selector.organization)

        async for repo, branch in _get_repos_and_branches_for_selector(
            file_selector, path
        ):
            repo_map[repo].append(
                {
                    "organization": organization,
                    "path": path,
                    "skip_parsing": skip_parsing,
                    "branch": branch,
                }
            )

    logger.info(
        f"Repository path map built for {len(repo_map)} repositories from {len(files)} file patterns."
    )

    return [
        ListFileSearchOptions(organization=organization, repo_name=repo, files=files)
        for repo, files in repo_map.items()
    ]


def match_file_path_against_glob_pattern(path: str, pattern: str) -> bool:
    """
    Match file path against a glob pattern using wcmatch's globmatch.
    Supports ** and other extended glob syntax.
    """
    return glob.globmatch(path, pattern, flags=glob.GLOBSTAR | glob.IGNORECASE)


def determine_api_client_type_by_file_size(size: int) -> GithubClientType:
    return (
        GithubClientType.GRAPHQL
        if size <= GRAPHQL_MAX_FILE_SIZE
        else GithubClientType.REST
    )


def filter_github_tree_entries_by_pattern(
    tree: List[Dict[str, Any]], pattern: str
) -> List[Dict[str, Any]]:
    """Filter GitHub tree blobs by type and size."""

    matched_files = []

    for entry in tree:
        type_ = entry["type"]
        path = entry["path"]
        size = entry.get("size", 0)

        if (
            type_ == "blob"
            and size <= MAX_FILE_SIZE
            and match_file_path_against_glob_pattern(path, pattern)
        ):
            fetch_method = determine_api_client_type_by_file_size(size)
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

    return {
        "url": url,
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
        file_{file_index}: object(expression: "{branch}:{path}") {{
            ... on Blob {{
                text
                byteSize
            }}
        }}
        """
        for file_index, path in enumerate(file_paths)
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
            if match_file_path_against_glob_pattern(file_path, pattern.path):
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


def extract_file_paths_and_metadata(
    files: List[Dict[str, Any]],
) -> tuple[list[str], dict[str, bool]]:
    file_paths = []
    file_metadata = {}

    for file in files:
        file_path = file["file_path"]
        file_paths.append(file_path)
        file_metadata[file_path] = file["skip_parsing"]

    return file_paths, file_metadata


def deep_dict(d: Union[DefaultDict[str, Any], Dict[str, Any], list[Any], Any]) -> Any:
    if isinstance(d, defaultdict):
        return {k: deep_dict(v) for k, v in d.items()}
    return d
