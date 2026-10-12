import fnmatch
from asyncio import Semaphore
from functools import partial
from httpx import HTTPError, HTTPStatusError
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Set, TYPE_CHECKING
from loguru import logger
from integration import BitbucketFilePattern
from bitbucket_cloud.helpers.exceptions import (
    BitbucketFileReadError,
    BitbucketFileWalkError,
)
from bitbucket_cloud.helpers.folder import get_parts_before_wildcard
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from initialize_client import init_client
from bitbucket_cloud.helpers.file_kind_live_event import (
    FileObject,
    check_and_load_file_prefix,
    parse_file,
)

if TYPE_CHECKING:
    from bitbucket_cloud.client import BitbucketClient

GLOBAL_PATHS = ["*/", "*", "**/*", "**", ""]
# A dead credential and an exhausted quota are about every repository still to be
# walked, not about this one.
WALK_STOPPING_STATUSES = (401, 429)
# Bitbucket lists one level when this is omitted. No ceiling is published and none was
# found - 10000, 1e6 and 1e8 are all accepted unclamped - so this only has to exceed
# the deepest tree.
MAX_LISTING_DEPTH = 10000
# Ours, not Bitbucket's: it publishes no limit for /src content. Matches
# github/core/exporters/file_exporter/utils.py.
MAX_FILE_SIZE = 1024 * 1024
# Bitbucket publishes no concurrent-request guidance and sends no x-ratelimit header on
# a 200, so these are the only bound on fan-out. Listings are also metered against the
# shared 980/hr window; content fetches are metered only under MultiTokenAuth, which is
# the one auth mode with a file_token_manager, so for the other two these are the whole
# of it. Serial was measured 10x slower over 30 repositories.
MAX_CONCURRENT_REPOSITORIES = 10
MAX_CONCURRENT_FILE_FETCHES = 20
# Without this the entry's commit carries no repository at all, and
# .metadata.commit.repository.* stops resolving for mappings written against search.
REPOSITORY_EXPANSION = "+values.commit.repository.mainbranch.name"


def normalize_directory_path(path: str) -> str:
    """Strip leading and trailing slashes so path variants match equivalently.

    ``hello/world``, ``/hello/world``, ``/hello/world/``, and ``hello/world/``
    all normalize to ``hello/world``. Root ``/`` and empty become ``""``.
    """
    return path.strip("/")


def escape_bbql_string(value: str) -> str:
    """Escape a value for use inside a double-quoted BBQL string.

    An unescaped quote makes Bitbucket answer 500 with an HTML body, which costs the
    whole repository's listing, and a configured filename is free text.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_source_filter(filenames: List[str]) -> str:
    """One Source API query covering every configured filename.

    ``type="commit_file"`` does more than exclude directories: only file entries carry
    ``size``, which the walk indexes directly.
    """
    clauses = " OR ".join(f'path~"{escape_bbql_string(name)}"' for name in filenames)
    return f'type="commit_file" AND ({clauses})'


def build_listing_root(path: str) -> str:
    """The directory to list, derived from a configured path pattern.

    Everything before the first wildcard is a real directory and narrows the listing;
    the rest is matched client-side. Every value in ``GLOBAL_PATHS`` reduces to the
    repository root.
    """
    return "/".join(get_parts_before_wildcard(normalize_directory_path(path)))


def repository_matches(repo: Dict[str, Any], configured_repositories: Set[str]) -> bool:
    """Whether a repository is one of the configured ones.

    A configured value may be the slug, the display name, or the display name with
    spaces hyphenated, in any case, so the caller passes the set lower-cased.
    """
    display_name = repo["name"]
    identifiers = {repo["slug"], display_name, display_name.replace(" ", "-")}
    return any(
        identifier.lower() in configured_repositories for identifier in identifiers
    )


def select_matching_files(
    entries: List[Dict[str, Any]],
    file_pattern: BitbucketFilePattern,
    repo_slug: str,
) -> List[Dict[str, Any]]:
    """The entries on one listing page whose content should be fetched.

    The server filter is a case-insensitive substring match that crosses directory
    separators, so it returns more than the configured filenames and
    ``validate_file_match`` is what narrows it. The size cap reads the listing's own
    ``size``, so an oversized file costs no content fetch.
    """
    selected = []
    for entry in entries:
        file_path = entry["path"]
        if not any(
            validate_file_match(file_path, filename, file_pattern.path)
            for filename in file_pattern.filenames
        ):
            logger.debug(
                f"{file_path} in {repo_slug} matches no configured filename, skipping"
            )
            continue
        # Excluded by policy, not unreadable: letting reconciliation delete its entity is correct.
        if entry["size"] > MAX_FILE_SIZE:
            logger.warning(
                f"Skipping {file_path} in {repo_slug}, {entry['size']} bytes "
                f"exceeds the {MAX_FILE_SIZE} byte limit"
            )
            continue
        selected.append(entry)
    return selected


def _record_or_stop(error: Exception, failures: List[Exception], context: str) -> None:
    """Record a failed read, or end the walk when the cause is not about this read.

    A dead credential and an exhausted quota apply to every repository still to be
    walked, so they stop it now and carry everything collected so far; anything else
    costs one file or one repository and the walk finishes without it.
    """
    if (
        isinstance(error, HTTPStatusError)
        and error.response.status_code in WALK_STOPPING_STATUSES
    ):
        raise BitbucketFileWalkError(
            f"Stopping the walk at {context}: {error}. This applies to every repository "
            f"still to be walked, not to this one."
        ) from ExceptionGroup("Unreadable files and repositories", failures + [error])
    logger.warning(
        f"Recording {context} as unreadable and continuing the walk: {error}"
    )
    failures.append(error)


async def _walk_repository(
    client: "BitbucketClient",
    repo: Dict[str, Any],
    file_pattern: BitbucketFilePattern,
    listing_root: str,
    source_filter: str,
    failures: List[Exception],
    fetches: Semaphore,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """List one repository's matching files and yield the content of each.

    ``listing_root`` and ``source_filter`` are derived from ``file_pattern`` and are
    passed in because they are the same for every repository in the workspace; the
    pattern itself is still needed for the matcher and for skip_parsing. A failed
    listing is recorded here rather than raised, because this runs as one of several
    concurrent walks and an exception would cancel the others.
    """
    repo_slug = repo["slug"]
    try:
        async for entries in client.get_directory_contents(
            repo_slug,
            repo["mainbranch"]["name"],
            listing_root,
            max_depth=MAX_LISTING_DEPTH,
            params={"q": source_filter, "fields": REPOSITORY_EXPANSION},
            raise_on_missing=True,
        ):
            tasks = [
                semaphore_async_iterator(
                    fetches,
                    partial(
                        retrieve_file_content,
                        repo,
                        entry,
                        file_pattern.skip_parsing,
                        failures,
                    ),
                )
                for entry in select_matching_files(entries, file_pattern, repo_slug)
            ]
            async for file_result in stream_async_iterators_tasks(*tasks):
                yield [file_result]
    # Only this catches a transport failure, which never reaches the client's own except.
    except HTTPError as e:
        _record_or_stop(e, failures, repo_slug)


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Discover files by listing each repository through Bitbucket's Source API."""
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file discovery")
        return

    listing_root = build_listing_root(file_pattern.path)
    source_filter = build_source_filter(file_pattern.filenames)
    logger.info(
        f"Discovering files with filter '{source_filter}' from root '{listing_root}'"
    )

    walked = 0
    matched = 0
    client = init_client()
    configured_repositories = {name.lower() for name in file_pattern.repos}
    if not configured_repositories:
        logger.warning("No repositories configured, listing the entire workspace")
    failures: List[Exception] = []

    listings = Semaphore(MAX_CONCURRENT_REPOSITORIES)
    fetches = Semaphore(MAX_CONCURRENT_FILE_FETCHES)

    # Shares the repository kind's cached listing when that kind configures neither
    # userRole nor repoQuery, since build_repo_params then also passes {} - the cache key
    # is the repr of the params, so any other value is a second full workspace listing.
    async for repositories in client.get_repositories(params={}):
        selected = []
        for repo in repositories:
            # A repository with no commits answers 404 "Commit not found" on its
            # listing, which is not a tolerated body.
            if not repo["size"]:
                logger.debug(f"Repository {repo['slug']} has no commits, skipping")
                continue
            if configured_repositories and not repository_matches(
                repo, configured_repositories
            ):
                logger.debug(
                    f"Repository {repo['slug']} is not in the configured repositories, skipping"
                )
                continue
            selected.append(repo)

        walked += len(selected)
        tasks = [
            semaphore_async_iterator(
                listings,
                partial(
                    _walk_repository,
                    client,
                    repo,
                    file_pattern,
                    listing_root,
                    source_filter,
                    failures,
                    fetches,
                ),
            )
            for repo in selected
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            matched += len(batch)
            yield batch

    if not matched and not failures:
        logger.warning(
            f"Walked {walked} repositories and matched no files for "
            f"{file_pattern.filenames} under '{file_pattern.path}'. A resync that "
            f"ends here with no error lets reconciliation delete every file entity."
        )

    if failures:
        raise BitbucketFileWalkError(
            f"{len(failures)} read {'failure' if len(failures) == 1 else 'failures'} "
            f"walking {file_pattern.filenames} under '{file_pattern.path}'"
        ) from ExceptionGroup("Unreadable files and repositories", failures)


async def retrieve_file_content(
    repo: Dict[str, Any],
    entry: Dict[str, Any],
    skip_parsing: bool,
    failures: List[Exception],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Retrieve the content of a single listed file.

    The repository is passed rather than read back out of the entry: the listing carries
    the authoritative slug, where the entry's embedded repository object carries only a
    display name. ``failures`` is the caller's list and this appends to it rather than
    raising, because raising here cancels the other fetches in flight for the page.
    """
    file_path = entry["path"]
    repo_slug = repo["slug"]
    branch = repo["mainbranch"]["name"]

    logger.info(f"Retrieving contents for {file_path} in {repo_slug}")
    client = init_client()
    # Recorded, not raised: an exception here cancels this page's other fetches, which is
    # what a 401 or 429 wants and nothing else does.
    try:
        file_content = await client.get_repository_files(repo_slug, branch, file_path)
    except HTTPError as e:
        _record_or_stop(e, failures, f"{file_path} in {repo_slug}")
        return
    if file_content is None:
        _record_or_stop(
            BitbucketFileReadError(
                f"Bitbucket returned no content for {file_path} in repository "
                f"{repo_slug} on branch {branch}"
            ),
            failures,
            f"{file_path} in {repo_slug}",
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
            "metadata": entry,
        }
    else:
        result = await check_and_load_file_prefix(
            file_content,
            str(parent_directory),
            repo_slug,
            branch,
            entry,
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
