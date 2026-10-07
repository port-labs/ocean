import fnmatch
import os
from httpx import HTTPStatusError, TransportError
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator
from loguru import logger
from integration import BitbucketFilePattern
from bitbucket_cloud.helpers.exceptions import (
    BitbucketFileReadError,
    BitbucketFileWalkError,
)
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from initialize_client import init_client
from bitbucket_cloud.helpers.file_kind_live_event import (
    FileObject,
    check_and_load_file_prefix,
    parse_file,
)

JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")
GLOBAL_PATHS = ["*/", "*", "**/*", "**", ""]
# A failed read of one file reports it and the walk carries on, because the kind ends in
# error either way and the readable files are worth keeping. Two statuses are not about
# the file at all: a dead credential and an exhausted quota apply to every repository
# still to be walked, so they stop it now rather than failing another few hundred times.
WALK_STOPPING_STATUSES = (401, 429)


def _repository_slug(repo_info: Dict[str, Any]) -> str:
    """A guess at the repository's URL slug, from its display name.

    It is wrong whenever the real slug is not the display name with spaces hyphenated -
    a renamed repository, or a name containing punctuation. The authoritative slug is in
    this same payload as ``full_name``; swapping to it changes which URL every content
    fetch addresses, so it is its own change rather than part of this one.
    """
    return repo_info["name"].replace(" ", "-")


def normalize_directory_path(path: str) -> str:
    """Strip leading and trailing slashes so path variants match equivalently.

    ``hello/world``, ``/hello/world``, ``/hello/world/``, and ``hello/world/``
    all normalize to ``hello/world``. Root ``/`` and empty become ``""``.
    """
    return path.strip("/")


def extract_filename_extension(filename: str) -> str:
    """Return a filename's extension without the leading dot.

    Dotfiles such as ``.nvmrc`` have no extension. ``os.path.splitext`` keeps
    the leading dot on the name, so those files are not dropped from Bitbucket
    code search by an ``ext:`` qualifier built from the rest of the name.
    """
    extension = os.path.splitext(filename)[1]
    if extension.startswith("."):
        return extension[1:]
    return extension


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

    search_terms.append(f"path:{normalize_directory_path(path) or '/'}")

    if extension:
        search_terms.append(f"ext:{extension}")

    return " ".join(search_terms)


def _report_unreadable_file(
    error: Exception, failures: List[Exception], file_info: Dict[str, Any]
) -> None:
    repository = _repository_slug(file_info["commit"]["repository"])
    logger.warning(
        f"Recording {file_info['path']} in {repository} as unreadable: {error}"
    )
    failures.append(error)


async def _collect_walk_failures(
    task: AsyncGenerator[Dict[str, Any], None],
    failures: List[Exception],
    file_info: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Report a file that cannot be read and carry on with the rest of the walk.

    Discovery has already said this file exists, and a content fetch cannot tell a file
    deleted since then from one it is not allowed to read. Reporting either as absence
    would let reconciliation delete the entity, which is the failure this change exists
    to stop, so both end the kind in error - but only once the walk has finished, so
    every readable file still lands and every failure is named. Each failure is appended
    to the caller's ``failures`` list, which the caller reads when the walk is drained.
    """
    try:
        async for file_result in task:
            yield file_result
    except HTTPStatusError as e:
        if e.response.status_code in WALK_STOPPING_STATUSES:
            logger.error(
                f"Stopping the walk at {file_info['path']}: {e}. This applies to every "
                f"repository still to be walked, not to this file."
            )
            raise
        _report_unreadable_file(e, failures, file_info)
    except BitbucketFileReadError as e:
        _report_unreadable_file(e, failures, file_info)
    except TransportError as e:
        _report_unreadable_file(e, failures, file_info)


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Process file patterns and retrieve matching files using Bitbucket's search API."""
    logger.info(
        f"Searching for files in {len(file_pattern.repos) if file_pattern.repos else 'all'} repositories with pattern: {file_pattern.path}"
    )

    path_to_search = file_pattern.path

    if not file_pattern.repos:
        logger.warning("No repositories provided, searching entire workspace")
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file search")
        return

    failures: List[Exception] = []

    for filename in file_pattern.filenames:
        search_query = build_search_terms(
            filename=filename,
            repos=file_pattern.repos,
            path=path_to_search if path_to_search not in GLOBAL_PATHS else "/",
            extension=extract_filename_extension(filename),
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
                        _collect_walk_failures(
                            retrieve_file_content(file_info, file_pattern.skip_parsing),
                            failures,
                            file_info,
                        )
                    )

            async for file_results in stream_async_iterators_tasks(*tasks):
                yield [file_results]

    if failures:
        raise BitbucketFileWalkError(
            f"{len(failures)} {'file' if len(failures) == 1 else 'files'} "
            f"could not be read while walking "
            f"{file_pattern.filenames} under '{file_pattern.path}'"
        ) from ExceptionGroup("Unreadable files", failures)


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
    file_path = file_info["path"]
    repo_info = file_info["commit"]["repository"]
    repo_slug = _repository_slug(repo_info)
    branch = repo_info["mainbranch"]["name"]

    logger.info(f"Retrieving contents for file: {file_path}")
    bitbucket_client = init_client()
    file_content = await bitbucket_client.get_repository_files(
        repo_slug, branch, file_path
    )
    if file_content is None:
        raise BitbucketFileReadError(
            f"Bitbucket returned no content for {file_path} in repository {repo_slug} "
            f"on branch {branch}"
        )
    parent_directory = Path(file_path).parent
    if not skip_parsing:
        file_content = parse_file(file_content, file_path)

    result: FileObject
    if skip_parsing or not isinstance(file_content, (dict, list)):
        result = {
            "content": file_content,
            "repo": repo_info,
            "branch": branch,
            "metadata": file_info,
        }
    else:
        result = await check_and_load_file_prefix(
            file_content,
            str(parent_directory),
            repo_slug,
            branch,
            file_info,
            repo_info,
            branch,
        )
    yield dict(result)


def validate_file_match(file_path: str, filename: str, expected_path: str) -> bool:
    """Validate if the file path and filename match the expected patterns."""
    if not file_path.endswith(filename):
        return False

    if (not expected_path or expected_path == "/") and file_path == filename:
        return True

    if expected_path in GLOBAL_PATHS:
        expected_path = "*/"

    dir_path = normalize_directory_path(file_path[: -len(filename)])
    expected_path = normalize_directory_path(expected_path)
    return fnmatch.fnmatch(dir_path, expected_path)
