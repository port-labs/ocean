import fnmatch
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator
from loguru import logger
from integration import BitbucketFilePattern
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from initialize_client import init_client
from bitbucket_cloud.helpers.file_kind_live_event import (
    check_and_load_file_prefix,
    parse_file,
)


JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")


def build_search_terms(
    filename: str, repos: List[str] | None, path: str, extension: str
) -> str:
    """
    This function builds search terms for Bitbucket's search API.
    The entire workspace is searched for the filename if repos is not provided.
    If repos are provided, only the repos specified are searched.
    The path and extension are required to tailor the search so results
    are relevant to the file kind.

    Args:
        filename (str): The filename to search for.
        repos (List[str] | None): The repositories to search in.
        path (str): The path to search in.
        extension (str): The extension to search for.

    Returns:
        str: The search terms for Bitbucket's search API.
    """
    search_terms = [f'"{filename}"']
    if repos:
        repo_filters = " ".join(f"repo:{repo}" for repo in repos)
        search_terms.append(f"{repo_filters}")

    search_terms.append(f"path:{path}")

    if extension:
        search_terms.append(f"ext:{extension}")

    return " ".join(search_terms)


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Process file patterns and retrieve matching files using Bitbucket's search API."""
    logger.info(
        f"Searching for files in {len(file_pattern.repos) if file_pattern.repos else 'all'} repositories with pattern: {file_pattern.path}"
    )

    if not file_pattern.repos:
        logger.warning("No repositories provided, searching entire workspace")
    if not file_pattern.path:
        logger.info("Path is required, skipping file search")
        return
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file search")
        return

    for filename in file_pattern.filenames:
        search_query = build_search_terms(
            filename=filename,
            repos=file_pattern.repos,
            path=file_pattern.path,
            extension=filename.split(".")[-1],
        )
        logger.debug(f"Constructed search query: {search_query}")
        bitbucket_client = init_client()
        async for search_results in bitbucket_client.search_files(search_query):
            tasks = []
            for result in search_results:
                if len(result["path_matches"]) >= 1:
                    file_info = result["file"]
                    file_path = file_info["path"]

                    if not validate_file_match(file_path, filename, file_pattern.path):
                        logger.debug(
                            f"Skipping file {file_path} as it doesn't match expected patterns"
                        )
                        continue

                    tasks.append(
                        retrieve_file_content(file_info, file_pattern.skip_parsing)
                    )

            async for file_results in stream_async_iterators_tasks(*tasks):
                yield [file_results]


async def retrieve_file_content(
    file_info: Dict[str, Any],
    skip_parsing: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Retrieve the content of a single file from Bitbucket.

    Args:
        file_info (Dict[str, Any]): Information about the file to retrieve

    Yields:
        Dict[str, Any]: Dictionary containing the file content and metadata
    """
    file_path = file_info.get("path", "")
    repo_info = file_info["commit"]["repository"]
    repo_slug = repo_info["name"].replace(" ", "-")
    branch = repo_info["mainbranch"]["name"]

    logger.info(f"Retrieving contents for file: {file_path}")
    bitbucket_client = init_client()
    file_content = await bitbucket_client.get_repository_files(
        repo_slug, branch, file_path
    )
    parent_directory = Path(file_path).parent
    if not skip_parsing:
        file_content = parse_file(file_content, file_path)
        result = await check_and_load_file_prefix(
            file_content,
            str(parent_directory),
            repo_slug,
            branch,
            file_info,
            repo_info,
            branch,
        )
    else:
        result = {
            "content": file_content,
            "repo": repo_info,
            "branch": branch,
            "metadata": file_info,
        }
    yield dict(result)


def validate_file_match(file_path: str, filename: str, expected_path: str) -> bool:
    """Validate if the file path and filename match the expected patterns."""
    if not file_path.endswith(filename):
        return False

    if (not expected_path or expected_path == "/") and file_path == filename:
        return True

    dir_path = file_path[: -len(filename)]
    dir_path = dir_path.rstrip("/")
    expected_path = expected_path.rstrip("/")
    return fnmatch.fnmatch(dir_path, expected_path)
