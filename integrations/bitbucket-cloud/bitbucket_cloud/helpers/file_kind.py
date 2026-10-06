import asyncio
from functools import partial
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator
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
from bitbucket_cloud.helpers.utils import (
    matches_configured_file,
    normalize_directory_path,
)
from bitbucket_cloud.helpers.file_kind_live_event import (
    FileObject,
    check_and_load_file_prefix,
    parse_file,
)

COMMIT_FILE_TYPE = "commit_file"
SKIPPED_REPOSITORY_EXAMPLES = 5

MAX_CONCURRENT_REPOSITORIES = 10
MAX_CONCURRENT_FILE_FETCHES = 20

FILE_BATCH_SIZE = 100

MAX_FILE_SIZE = 1024 * 1024

# Defaults to the root's immediate entries. 10000 measured accepted 2026-10-03.
MAX_LISTING_DEPTH = 10000

REPOSITORY_FIELDS = "+values.commit.repository.mainbranch.name"


def escape_bbql_string(value: str) -> str:
    """Escape a value for a double-quoted BBQL string literal.

    The selector accepts free text, and an unescaped quote malforms the whole query,
    which costs the entire repository rather than the one filename. Measured
    2026-10-06 against a public workspace: `path~"RE"ADME"` answers HTTP 500 with an
    HTML body, `path~"RE\"ADME"` and `path~"a\\b"` both answer 200 and match
    literally.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_file_filter(filenames: List[str]) -> str:
    """Build the BBQL filter that selects matching files server-side.

    One query serves every configured filename. ``path~`` is a *contains* match, so
    results are still narrowed by ``validate_file_match``.
    """
    path_clauses = " OR ".join(
        f'path~"{escape_bbql_string(filename)}"' for filename in filenames
    )
    return f'type="{COMMIT_FILE_TYPE}" AND ({path_clauses})'


def build_listing_root(path: str) -> str:
    """Return the fixed directory prefix to list from, before the first glob segment.

    This narrows where the walk starts; it never narrows how deep it goes.
    """
    return "/".join(get_parts_before_wildcard(normalize_directory_path(path)))


def repository_matches(
    repo: Dict[str, Any], configured_repositories: List[str]
) -> bool:
    """Match a repository against the configured ``repos`` list.

    The code search path matched the slug case-insensitively; display names and their
    hyphenated form are accepted too, so no configured value stops matching.
    """
    if not configured_repositories:
        return True

    name = repo["name"]
    candidates = {
        repo["slug"].lower(),
        name.lower(),
        name.replace(" ", "-").lower(),
    }
    return any(value.lower() in candidates for value in configured_repositories)


def has_main_branch(repo: Dict[str, Any]) -> bool:
    """An empty or uninitialised repository has no tree to list."""
    return bool(repo.get("mainbranch"))


def log_skipped_repositories(skipped_repositories: List[str]) -> None:
    if not skipped_repositories:
        return

    examples = ", ".join(skipped_repositories[:SKIPPED_REPOSITORY_EXAMPLES])
    if len(skipped_repositories) > SKIPPED_REPOSITORY_EXAMPLES:
        remaining = len(skipped_repositories) - SKIPPED_REPOSITORY_EXAMPLES
        examples = f"{examples}, ... (+{remaining} more)"
    logger.info(
        f"Skipping {len(skipped_repositories)} repositories without a main branch "
        f"during file discovery (examples: {examples})"
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
    skipped_repositories: List[str] = []
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
                skipped_repositories.append(repo["slug"])
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
        except ExceptionGroup as error:  # noqa: F821
            failures.extend(error.exceptions)

    if batch:
        yield batch

    log_skipped_repositories(skipped_repositories)

    if failures:
        raise OceanAbortException(
            f"File discovery failed for {len(failures)} of {walked} repositories"
        ) from ExceptionGroup(  # noqa: F821
            "File discovery failures", failures
        )

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

    # A 404 is an absent directory or an unreadable repository, indistinguishably. With
    # no sub-path nothing can legitimately be absent, so it is a failure; with one it is
    # the common case, and separating them costs a request per repository without it.
    listing = client.get_directory_contents(
        repo_slug,
        branch,
        listing_root,
        max_depth=MAX_LISTING_DEPTH,
        params={"q": file_filter, "fields": REPOSITORY_FIELDS},
        raise_on_missing=not listing_root,
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
                if not matches_configured_file(
                    file_path, file_pattern.filenames, file_pattern.path
                ):
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
                yield [file_results]
    # What reaches here: HTTPStatusError for any status but an accepted 404;
    # httpx.HTTPError for transport faults, which _send_api_request re-raises;
    # json.JSONDecodeError, which it does not catch, from a non-JSON listing body;
    # KeyError if an entry or repo lacks a field the q filter should have guaranteed;
    # and anything raised fetching or parsing one file. The catch stays broad on
    # purpose - it only attaches the repository and re-raises, and a narrower tuple
    # would let an unlisted type through with no slug in the log.
    except Exception as error:
        logger.error(
            f"File discovery failed for repository {repo_slug} on branch {branch}: "
            f"{error}"
        )
        raise


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
        # Omitting it would not protect the entity: the resync completes and
        # reconciliation deletes it. Failing the repository is what preserves it.
        raise RuntimeError(
            f"{repo_slug}/{file_path} was listed at {commit_hash[:12]} but its "
            "content could not be read"
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
