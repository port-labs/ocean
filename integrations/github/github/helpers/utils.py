from functools import lru_cache
from enum import StrEnum
import re
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
)

from pydantic import BaseModel
from loguru import logger
from typing import TYPE_CHECKING

from port_ocean.utils import cache
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result
from github.core.options import (
    ListOrganizationOptions,
    ListRepositoryOptions,
)
from wcmatch import glob


if TYPE_CHECKING:
    from github.clients.http.base_client import AbstractGithubClient
    from integration import RepositoryBranchMapping
    from github.core.exporters.abstract_exporter import AbstractGithubExporter


GLOB_COMPILE_FLAGS = glob.EXTGLOB | glob.BRACE | glob.DOTMATCH | glob.IGNORECASE
GLOB_SPLIT_RE = re.compile(r"[*?\[\]\{\}\(\)\|@]")


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    """Enum for GitHub resource kinds."""

    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    FOLDER = "folder"
    USER = "user"
    TEAM = "team"
    WORKFLOW = "workflow"
    WORKFLOW_RUN = "workflow-run"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    RELEASE = "release"
    TAG = "tag"
    BRANCH = "branch"
    ENVIRONMENT = "environment"
    DEPLOYMENT = "deployment"
    DEPENDABOT_ALERT = "dependabot-alert"
    CODE_SCANNING_ALERT = "code-scanning-alerts"
    SECRET_SCANNING_ALERT = "secret-scanning-alerts"
    FILE = "file"
    COLLABORATOR = "collaborator"


def enrich_with_repository(
    response: Dict[str, Any], repo_name: str, key: str = "__repository"
) -> Dict[str, Any]:
    """Helper function to enrich response with repository information.
    Args:
        response: The response to enrich
        repo_name: The name of the repository
        key: The key to use for repository information (defaults to "__repository")
    Returns:
        The enriched response
    """
    response[key] = repo_name
    return response


def parse_github_options(
    params: dict[str, Any],
) -> tuple[str | None, str, dict[str, Any]]:
    """Extract the repository name and other parameters from the options."""
    organization = params.pop("organization")
    repo_name = params.pop("repo_name", None)
    return repo_name, organization, params


async def fetch_commit_diff(
    client: "AbstractGithubClient",
    organization: str,
    repo_name: str,
    before_sha: str,
    after_sha: str,
) -> Dict[str, Any]:
    """
    Fetch the commit comparison data from GitHub API.
    """
    resource = f"{client.base_url}/repos/{organization}/{repo_name}/compare/{before_sha}...{after_sha}"
    response = await client.send_api_request(resource)

    logger.info(
        f"Found {len(response['files'])} files in commit diff of organization: {organization}"
    )

    return response


def extract_changed_files(
    files: List[Dict[str, Any]],
) -> Tuple[Set[str], Set[str]]:
    """
    Extract files that were changed in the push event.
    Returns a set of file paths that were added, modified, or removed.
    """
    deleted_files: Set[str] = set()
    updated_files: Set[str] = set()

    for file in files:
        (deleted_files if file.get("status") == "removed" else updated_files).add(
            file["filename"]
        )

    return deleted_files, updated_files


def enrich_with_tag_name(response: Dict[str, Any], tag_name: str) -> Dict[str, Any]:
    """Helper function to enrich response with tag name information."""
    response["name"] = tag_name
    return response


def enrich_with_commit(
    response: Dict[str, Any], commit_object: Dict[str, Any]
) -> Dict[str, Any]:
    """Helper function to enrich response with commit information."""
    response["commit"] = commit_object
    return response


def create_search_params(repos: Iterable[str]) -> list[str]:
    """Create search query strings that fits into Github search string limitations.

    Limitations:
        - A search query can be up to 256 characters.
        - A query can contain a maximum of 5 `OR` operators.

    """
    max_operators = 5
    max_repos_in_query = max_operators + 1
    max_search_string_len = 256

    tokens: list[str] = []
    seen: set[str] = set()
    for entry in repos:
        token = extract_search_token(entry)
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)

    search_strings: list[str] = []
    chunk: list[str] = []
    current_query = ""
    for token in tokens:
        repo_query_part = f"{token} in:name"
        if len(repo_query_part) > max_search_string_len:
            logger.warning(
                f"Repository name '{token}' is too long to fit in a search query."
            )
            continue

        if not chunk:
            chunk.append(token)
            current_query = repo_query_part
            continue

        next_query = f"{current_query} OR {repo_query_part}"

        if (
            len(chunk) + 1 > max_repos_in_query
            or len(next_query) > max_search_string_len
        ):
            search_strings.append(current_query)
            chunk = [token]
            current_query = repo_query_part
        else:
            chunk.append(token)
            current_query = next_query

    if chunk:
        search_strings.append(current_query)

    return search_strings


@cache_iterator_result()
async def search_for_repositories(
    client: "AbstractGithubClient", organization: str, repos: Iterable[str]
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """Search Github for a list of repositories and cache the result"""

    tasks = []
    for search_string in create_search_params(repos):
        logger.debug(f"creating a search task for search string: {search_string}")
        query = f"org:{organization} {search_string} fork:true"
        url = f"{client.base_url}/search/repositories"
        params = {"q": query}
        tasks.append(client.send_paginated_request(url, params=params))

    async for search_result in stream_async_iterators_tasks(*tasks):
        repos = search_result["items"]
        logger.info(f"Found {len(repos)} repositories for organization {organization}")
        yield repos


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


def is_glob(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[]{}()@|")


def extract_search_token(pattern: str) -> str | None:
    segments = GLOB_SPLIT_RE.split(pattern)
    valid = [s.strip() for s in segments if any(c.isalnum() for c in s)]
    return max(valid, key=len) if valid else None


@lru_cache(maxsize=1024)
def get_compiled_pattern(
    pattern: str, flags: int = GLOB_COMPILE_FLAGS
) -> "re.Pattern[str]":
    return glob.compile(pattern, flags=flags)


@cache.cache_coroutine_result()
async def get_repository_metadata(
    client: "AbstractGithubClient", organization: str, repo_name: str
) -> Dict[str, Any]:
    url = f"{client.base_url}/repos/{organization}/{repo_name}"
    logger.info(f"Fetching metadata for repository: {repo_name} from {organization}")
    return await client.send_api_request(url)


async def iterate_org_repos_and_branches(
    selector: BaseModel,
    repo_exporter: "AbstractGithubExporter[Any]",
    repo_type: str,
    org_login: str,
) -> AsyncGenerator[tuple[str, str, str, Optional[Dict[str, Any]]], None]:
    if selector.repos is None:
        logger.info(
            f"No repositories specified for selector '{selector}'. Fetching all '{repo_type}' repositories from '{org_login}'."
        )
        async for batch in repo_exporter.get_paginated_resources(
            ListRepositoryOptions(organization=org_login, type=repo_type)
        ):
            for repository in batch:
                logger.debug(
                    f"Fetched repository '{repository['name']}' with default branch '{repository['default_branch']}' in organization '{org_login}'."
                )
                yield repository["name"], repository[
                    "default_branch"
                ], org_login, repository
        return

    exact_repos: List["RepositoryBranchMapping"] = []
    glob_repos: List["RepositoryBranchMapping"] = []
    for repo_sel in selector.repos:
        (glob_repos if is_glob(repo_sel.name) else exact_repos).append(repo_sel)

    for repo_sel in exact_repos:
        repo_obj = await get_repository_metadata(
            repo_exporter.client, org_login, repo_sel.name
        )
        yield repo_sel.name, repo_sel.branch or repo_obj[
            "default_branch"
        ], org_login, repo_obj

    if not glob_repos:
        return

    logger.info(
        f"Resolving {len(glob_repos)} glob pattern repositories for organization '{org_login}': "
        f"{[repo_sel.name for repo_sel in glob_repos]}"
    )

    compiled_patterns: list[tuple["re.Pattern[str]", "RepositoryBranchMapping"]] = [
        (get_compiled_pattern(repo_sel.name), repo_sel) for repo_sel in glob_repos
    ]
    patterns = [repo_sel.name for repo_sel in glob_repos]
    async for search_batch in search_for_repositories(
        repo_exporter.client, org_login, patterns
    ):
        for repo in search_batch:
            repo_name = repo["name"]
            for compiled, repo_sel in compiled_patterns:
                if compiled.match(repo_name):
                    branch = repo_sel.branch or repo["default_branch"]
                    logger.info(
                        f"Glob match: repository '{repo_name}' matched pattern '{repo_sel.name}' "
                        f"with branch '{branch}' in organization '{org_login}'."
                    )
                    yield repo_name, branch, org_login, repo


async def get_repos_and_branches_for_selector(
    selector: BaseModel,
    org_exporter: "AbstractGithubExporter[Any]",
    repo_exporter: "AbstractGithubExporter[Any]",
    repo_type: str,
) -> AsyncGenerator[tuple[str, str, str, Optional[Dict[str, Any]]], None]:

    async for org_batch in org_exporter.get_paginated_resources(
        ListOrganizationOptions(organization=selector.organization)
    ):
        org_logins: list[str] = []
        for org in org_batch:
            org_login = org["login"]
            org_logins.append(org_login)

        if not org_logins:
            continue

        logger.info(
            f"Starting repository and branch iteration for organizations: {org_logins}"
        )

        tasks = [
            iterate_org_repos_and_branches(selector, repo_exporter, repo_type, login)
            for login in org_logins
        ]

        async for item in stream_async_iterators_tasks(*tasks):
            yield item
