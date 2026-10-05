import asyncio
import fnmatch
from http import HTTPStatus
from functools import partial
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator
from httpx import HTTPStatusError
from loguru import logger
from integration import BitbucketFilePattern
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
    stream_independent_async_iterators,
)
from initialize_client import init_client
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.helpers.folder import get_parts_before_wildcard
from bitbucket_cloud.helpers.file_kind_live_event import (
    FileObject,
    check_and_load_file_prefix,
    parse_file,
)

GLOBAL_PATHS = ["*/", "*", "**/*", "**", ""]
MAX_CONCURRENT_REPOSITORIES = 10
MAX_CONCURRENT_FILE_FETCHES = 20
FILE_BATCH_SIZE = 100
SKIPPED_REPOSITORY_EXAMPLES = 5

MAX_FILE_SIZE = 1024 * 1024  # 1MB limit in bytes

# The Source API returns only the listing root's immediate entries unless max_depth is set.
MAX_LISTING_DEPTH = 10000

# The listing does not return commit.repository at all unless it is requested. The
# branch name itself is already known from the repositories listing; this expansion
# exists solely so `.metadata.commit.repository.*` keeps resolving for mappings written
# against the code-search payload, which carried it. Measured: without this param eight
# commit.repository.* leaves are lost; requesting this one leaf returns all of them.
REPOSITORY_FIELDS = "+values.commit.repository.mainbranch.name"


def normalize_directory_path(path: str) -> str:
    """Strip leading and trailing slashes so path variants match equivalently.

    ``hello/world``, ``/hello/world``, ``/hello/world/``, and ``hello/world/``
    all normalize to ``hello/world``. Root ``/`` and empty become ``""``.
    """
    return path.strip("/")


COMMIT_FILE_TYPE = "commit_file"


def build_file_filter(filenames: List[str]) -> str:
    """Build the BBQL filter that selects matching files server-side.

    One query serves every configured filename. ``path~`` is a *contains* match, so
    results are still narrowed by ``validate_file_match``.
    """
    path_clauses = " OR ".join(f'path~"{filename}"' for filename in filenames)
    return f'type="{COMMIT_FILE_TYPE}" AND ({path_clauses})'


def build_listing_root(path: str) -> str:
    """Return the fixed directory prefix to list from, before the first glob segment.

    This narrows where the walk starts; it never narrows how deep it goes.
    """
    return "/".join(get_parts_before_wildcard(normalize_directory_path(path)))


def repository_matches(repo: Dict[str, Any], configured: List[str]) -> bool:
    """Match a repository against the configured ``repos`` list.

    The code search path matched the slug case-insensitively; display names and their
    hyphenated form are accepted too, so no configured value stops matching.
    """
    if not configured:
        return True

    name = repo["name"]
    candidates = {
        repo["slug"].lower(),
        name.lower(),
        name.replace(" ", "-").lower(),
    }
    return any(value.lower() in candidates for value in configured)


def has_main_branch(repo: Dict[str, Any]) -> bool:
    """An empty or uninitialised repository has no tree to list."""
    return bool(repo.get("mainbranch"))


def log_skipped_repositories(skipped: List[str]) -> None:
    if not skipped:
        return

    examples = ", ".join(skipped[:SKIPPED_REPOSITORY_EXAMPLES])
    if len(skipped) > SKIPPED_REPOSITORY_EXAMPLES:
        examples = (
            f"{examples}, ... (+{len(skipped) - SKIPPED_REPOSITORY_EXAMPLES} more)"
        )
    logger.info(
        f"Skipping {len(skipped)} repositories without a main branch during file "
        f"discovery (examples: {examples})"
    )


def matches_configured_file(file_path: str, file_pattern: BitbucketFilePattern) -> bool:
    return any(
        validate_file_match(file_path, filename, file_pattern.path)
        for filename in file_pattern.filenames
    )


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
    repository_params: Dict[str, Any],
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Discover matching files by listing each repository with a server-side filter."""
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file discovery")
        return

    # repoQuery / userRole narrow the walk server-side, so an empty `repos` list no
    # longer means the whole workspace is being walked.
    if not file_pattern.repos and not repository_params:
        logger.warning(
            "No repository filter configured, discovering files across the workspace"
        )

    client = init_client()
    file_filter = build_file_filter(file_pattern.filenames)
    listing_root = build_listing_root(file_pattern.path)
    logger.info(
        f"Discovering files with filter '{file_filter}' from root '{listing_root}'"
    )

    # Bounded at both levels: repositories being walked, and content fetches in flight
    # across all of them. The inner bound is shared, so it caps the whole kind.
    repository_semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_REPOSITORIES)
    file_semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_FILE_FETCHES)
    skipped: List[str] = []
    failures: List[Exception] = []
    batch: List[Dict[str, Any]] = []
    walked = 0
    discovered = 0

    async for repositories in client.get_repositories(params=repository_params):
        tasks = []
        for repo in repositories:
            if not repository_matches(repo, file_pattern.repos):
                logger.debug(
                    f"Skipping repository {repo['slug']} as it is not in "
                    f"{file_pattern.repos}"
                )
                continue

            if not has_main_branch(repo):
                skipped.append(repo["slug"])
                continue

            tasks.append(
                semaphore_async_iterator(
                    repository_semaphore,
                    partial(
                        process_repository_files,
                        repo,
                        file_pattern,
                        file_filter,
                        listing_root,
                        client,
                        file_semaphore,
                    ),
                )
            )

        if not tasks:
            logger.debug("No repositories in this batch matched the file pattern")
            continue

        walked += len(tasks)
        # Failures are carried across batches rather than raised here, so one bad
        # repository does not stop the batches still to come. Raising at the end leaves
        # the kind in error, which is what makes reconciliation skip its delete phase.
        try:
            async for file_results in stream_independent_async_iterators(
                *tasks, context="Bitbucket file discovery"
            ):
                discovered += len(file_results)
                batch.extend(file_results)
                if len(batch) >= FILE_BATCH_SIZE:
                    yield batch
                    batch = []
        except ExceptionGroup as error:
            failures.extend(error.exceptions)

    if batch:
        yield batch

    log_skipped_repositories(skipped)

    if failures:
        raise OceanAbortException(
            f"File discovery failed for {len(failures)} of {walked} repositories"
        ) from ExceptionGroup("File discovery failures", failures)

    if not walked:
        logger.warning("No repositories matched for file discovery")
    elif not discovered:
        logger.warning(
            f"Walked {walked} repositories and matched no files for filenames "
            f"{file_pattern.filenames} under path '{file_pattern.path}'"
        )


async def process_repository_files(
    repo: Dict[str, Any],
    file_pattern: BitbucketFilePattern,
    file_filter: str,
    listing_root: str,
    client: BitbucketClient,
    file_semaphore: asyncio.BoundedSemaphore,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """List one repository's tree and yield the files matching the pattern."""
    repo_slug = repo["slug"]
    branch = repo["mainbranch"]["name"]

    yielded_any = False
    listing = client.get_directory_contents(
        repo_slug,
        branch,
        listing_root,
        max_depth=MAX_LISTING_DEPTH,
        params={"q": file_filter, "fields": REPOSITORY_FIELDS},
        # Bitbucket answers 404 for an absent path, an unreadable repository, a bad
        # branch and a bad slug alike. Repositories without a main branch are already
        # excluded, so swallowing it would delete this repository's file entities
        # silently. Raise, and disambiguate the one ambiguous case below.
        raise_on_missing=True,
    )
    try:
        async for entries in listing:
            tasks = []
            for entry in entries:
                # The q filter asks for commit_file only, and directory entries carry no
                # size. Enforce it here rather than trusting the filter to have applied.
                if entry["type"] != COMMIT_FILE_TYPE:
                    logger.debug(
                        f"Skipping non-file entry {entry['path']} of type "
                        f"{entry['type']} in {repo_slug}"
                    )
                    continue

                file_path = entry["path"]
                if not matches_configured_file(file_path, file_pattern):
                    logger.debug(
                        f"Skipping file {file_path} as it doesn't match expected patterns"
                    )
                    continue

                if entry["size"] > MAX_FILE_SIZE:
                    logger.warning(
                        f"Skipping file {repo_slug}/{file_path} because it is "
                        f"{entry['size']} bytes, above the {MAX_FILE_SIZE} byte limit"
                    )
                    continue

                tasks.append(
                    semaphore_async_iterator(
                        file_semaphore,
                        partial(
                            retrieve_file_content,
                            entry,
                            repo,
                            branch,
                            file_pattern.skip_parsing,
                        ),
                    )
                )

            if not tasks:
                logger.debug(
                    f"No entries in this listing page of {repo_slug} matched "
                    f"{file_pattern.filenames}"
                )
                continue

            async for file_results in stream_async_iterators_tasks(*tasks):
                yielded_any = True
                yield [file_results]
    except HTTPStatusError as error:
        if await _listing_not_found_means_absent_path(
            error, client, repo_slug, branch, listing_root, yielded_any
        ):
            logger.info(
                f"Configured path '{listing_root}' is absent in {repo_slug}, "
                "treating as no matching files"
            )
            return
        raise


async def _listing_not_found_means_absent_path(
    error: HTTPStatusError,
    client: BitbucketClient,
    repo_slug: str,
    branch: str,
    listing_root: str,
    yielded_any: bool,
) -> bool:
    """Decide whether a failed listing means "no such directory" or a real failure.

    Bitbucket answers 404 for an absent directory, an unreadable repository, a bad
    branch and a bad slug alike, and the difference decides whether reconciliation
    deletes this repository's file entities. Only one case is genuinely ambiguous:
    a 404 on a configured sub-path before anything was yielded. Reading the root
    resolves it, at the cost of one extra call per repository.
    """
    if error.response.status_code != HTTPStatus.NOT_FOUND:
        return False

    if not listing_root:
        # Nothing under the root could be legitimately missing.
        return False

    if yielded_any:
        # Files already came back, so the path existed and this 404 is something else.
        return False

    return await _repository_root_is_readable(client, repo_slug, branch)


async def _repository_root_is_readable(
    client: BitbucketClient, repo_slug: str, branch: str
) -> bool:
    """Read the repository root, to tell an absent sub-path from an unreadable repo.

    A 404 on the root means the repository, branch or credential is the problem. Any
    other failure is not evidence either way and is left to the caller to surface.
    """
    try:
        async for _ in client.get_directory_contents(
            repo_slug, branch, "", max_depth=1, raise_on_missing=True
        ):
            break
    except HTTPStatusError as probe_error:
        status = probe_error.response.status_code
        if status != HTTPStatus.NOT_FOUND:
            raise
        logger.warning(
            f"Root listing of {repo_slug} on branch {branch} returned 404 - the "
            "repository, the branch or the credential's access to it is the problem, "
            "not the configured path"
        )
        return False
    return True


async def retrieve_file_content(
    file_entry: Dict[str, Any],
    repo: Dict[str, Any],
    branch: str,
    skip_parsing: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Retrieve the content of a single file from Bitbucket.

    Args:
        file_entry (Dict[str, Any]): A listing entry for the file to retrieve
        repo (Dict[str, Any]): The repository the file was listed from
        branch (str): The repository's main branch
        skip_parsing (bool): Return the raw content instead of parsing it

    Yields:
        Dict[str, Any]: Dictionary containing the file content and metadata
    """
    file_path = file_entry["path"]
    repo_slug = repo["slug"]
    commit_hash = file_entry["commit"]["hash"]

    logger.info(f"Retrieving contents for file: {file_path}")
    bitbucket_client = init_client()
    file_content = await bitbucket_client.get_repository_files(
        repo_slug, commit_hash, file_path
    )
    parent_directory = Path(file_path).parent
    if not skip_parsing:
        file_content = parse_file(file_content, file_path)

    result: FileObject
    if skip_parsing or not isinstance(file_content, (dict, list)):
        result = {
            "content": file_content,
            "repo": repo,
            "branch": branch,
            "metadata": file_entry,
        }
    else:
        result = await check_and_load_file_prefix(
            file_content,
            str(parent_directory),
            repo_slug,
            commit_hash,
            file_entry,
            repo,
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
