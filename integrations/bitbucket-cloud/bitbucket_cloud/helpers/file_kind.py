import asyncio
import fnmatch
from http import HTTPStatus
from functools import partial
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator, Optional
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
COMMIT_FILE_TYPE = "commit_file"
SKIPPED_REPOSITORY_EXAMPLES = 5

# Bitbucket Cloud publishes hourly quotas and no concurrency figure at all
# (support.atlassian.com/bitbucket-cloud/docs/api-request-limits, read 2026-10-06:
# raw file requests 5,000/hour, repository data access 1,000-10,000/hour, "a one-hour
# rolling window", nothing on simultaneous connections). The quotas are already
# enforced by RollingWindowLimiter from BitbucketRateLimiterConfig (980) and
# BitbucketFileRateLimiterConfig (4,980) in helpers/utils.py, so these two bounds exist
# to cap in-flight requests and resident file content, not to stay inside a quota.
# 10 repositories matches the Ocean baseline for the same work (github/main.py:151
# MAX_CONCURRENT_REPOS = 10); the 20 file fetches are shared across every repository
# being walked, so a wide workspace cannot multiply the per-repository fan-out.
MAX_CONCURRENT_REPOSITORIES = 10
MAX_CONCURRENT_FILE_FETCHES = 20

# Entities per yield; each yield is one Port upsert and one jq process-pool spin-up.
# Chosen to match client.PAGE_SIZE so one listing page flushes as one batch. No API
# limit applies.
FILE_BATCH_SIZE = 100

# Ours, not Bitbucket's - the Source API serves a file of any size. This is the Ocean
# file-kind convention, carried from
# github/core/exporters/file_exporter/utils.py:40, and bounds what a single entity can
# pull into memory and send to Port.
MAX_FILE_SIZE = 1024 * 1024

# The Source API returns only the listing root's immediate entries unless max_depth is
# set; the spec documents the default of 1 and no maximum. 10000 stands in for "every
# level" and was measured accepted, HTTP 200, on 2026-10-03.
MAX_LISTING_DEPTH = 10000

# One level answers whether the root is listable at all, which is all the probe asks.
ROOT_PROBE_DEPTH = 1

# A credential that cannot read the workspace fails every remaining repository the same
# way, so there is nothing to learn from walking them.
WALK_STOPPING_STATUSES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})

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


def stops_the_walk(error: BaseException) -> bool:
    """Whether a repository's failure means the remaining repositories are pointless.

    The failures that reach here are the listing's ``HTTPStatusError`` (the file kind
    asks for 404s to be raised), httpx transport errors, and anything raised while
    fetching or parsing one file. Only a credential rejection is workspace-wide:
    401 means the credential is bad and 403 means it lacks the scope or is blocked, and
    neither changes for the next repository. A 404 is already handled where it is
    raised, and a 429 has been retried by the transport before it gets here.
    """
    return (
        isinstance(error, HTTPStatusError)
        and error.response.status_code in WALK_STOPPING_STATUSES
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
            if stopping := [
                exception for exception in error.exceptions if stops_the_walk(exception)
            ]:
                logger.error(
                    f"Stopping file discovery after {len(stopping)} of {walked} "
                    f"repositories failed authorization. The credential cannot read "
                    f"this workspace, so the repositories still to come would fail "
                    f"the same way. First failure: {stopping[0]}"
                )
                break

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
                            client,
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
        # Bitbucket answers 404 for an absent directory, an unreadable repository, a
        # bad branch and a bad slug alike, and the difference decides whether
        # reconciliation deletes this repository's file entities. Only one case is
        # ambiguous: a 404 on a configured sub-path before anything was yielded.
        # Reading the root resolves it, at the cost of one extra call per repository.
        sub_path_may_be_absent = (
            error.response.status_code == HTTPStatus.NOT_FOUND
            and bool(listing_root)
            and not yielded_any
        )
        if sub_path_may_be_absent:
            if await read_repository_root(client, repo_slug, branch) is None:
                logger.error(
                    f"File discovery failed for repository {repo_slug}: neither "
                    f"'{listing_root}' nor the repository root could be listed on "
                    f"branch {branch}, so the repository, the branch or the "
                    f"credential's access to it is the problem, not the configured "
                    f"path"
                )
                raise
            logger.info(
                f"Configured path '{listing_root}' is absent in repository "
                f"{repo_slug}, treating as no matching files"
            )
            return
        logger.error(
            f"File discovery failed for repository {repo_slug} on branch {branch}: "
            f"{error}"
        )
        raise
    except Exception as error:
        logger.error(
            f"File discovery failed for repository {repo_slug} on branch {branch}: "
            f"{error}"
        )
        raise


async def read_repository_root(
    client: BitbucketClient, repo_slug: str, branch: str
) -> Optional[List[Dict[str, Any]]]:
    """Read the repository root listing, or None when the root itself is a 404.

    The caller decides what that means. Any status other than 404 is not evidence
    either way and is left to the caller to surface.
    """
    try:
        async for entries in client.get_directory_contents(
            repo_slug, branch, "", max_depth=ROOT_PROBE_DEPTH, raise_on_missing=True
        ):
            return entries
    except HTTPStatusError as probe_error:
        if probe_error.response.status_code != HTTPStatus.NOT_FOUND:
            raise
        return None
    return []


async def retrieve_file_content(
    file_entry: Dict[str, Any],
    repo: Dict[str, Any],
    branch: str,
    skip_parsing: bool,
    client: BitbucketClient,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Retrieve the content of a single file from Bitbucket.

    Args:
        file_entry (Dict[str, Any]): A listing entry for the file to retrieve
        repo (Dict[str, Any]): The repository the file was listed from
        branch (str): The repository's main branch
        skip_parsing (bool): Return the raw content instead of parsing it
        client (BitbucketClient): The client the repository was listed with

    Yields:
        Dict[str, Any]: Dictionary containing the file content and metadata
    """
    file_path = file_entry["path"]
    repo_slug = repo["slug"]
    commit_hash = file_entry["commit"]["hash"]

    logger.info(f"Retrieving contents for file: {file_path}")
    file_content = await client.get_repository_files(repo_slug, commit_hash, file_path)
    if file_content is None:
        logger.warning(
            f"Skipping {repo_slug}/{file_path} at {commit_hash[:12]}: the listing "
            "returned it but its content could not be read"
        )
        return

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


def filename_matches(file_path: str, filename: str) -> bool:
    """Match a configured filename against the tail of a repository-relative path.

    ``endswith`` on its own accepts ``airport.yml`` for a configured ``port.yml``, so
    the match has to land on a path boundary. A configured value that already carries
    directories, ``conf/README.md``, still matches at that boundary.
    """
    return file_path == filename or file_path.endswith(f"/{filename}")


def validate_file_match(file_path: str, filename: str, expected_path: str) -> bool:
    """Validate if the file path and filename match the expected patterns."""
    if not filename_matches(file_path, filename):
        return False

    if (not expected_path or expected_path == "/") and file_path == filename:
        return True

    if expected_path in GLOBAL_PATHS:
        expected_path = "*/"

    dir_path = normalize_directory_path(file_path[: -len(filename)])
    expected_path = normalize_directory_path(expected_path)
    return fnmatch.fnmatch(dir_path, expected_path)
