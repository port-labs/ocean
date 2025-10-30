from enum import StrEnum
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
import re
from loguru import logger
from typing import TYPE_CHECKING

from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result


if TYPE_CHECKING:
    from github.clients.http.base_client import AbstractGithubClient


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
    params: dict[str, Any]
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


def create_search_params(repos: Iterable[str], max_operators: int = 5) -> list[str]:
    """Create search query strings that fits into Github search string limitations.

    Limitations:
        - A search query can be up to 256 characters.
        - A query can contain a maximum of 5 `OR` operators.

    """
    search_strings = []
    if not repos:
        return []

    max_repos_in_query = max_operators + 1
    max_search_string_len = 256

    chunk: list[str] = []
    current_query = ""
    for repo in repos:
        repo_query_part = f"{repo} in:name"

        if len(repo_query_part) > max_search_string_len:
            logger.warning(
                f"Repository name '{repo}' is too long to fit in a search query."
            )
            continue

        if not chunk:
            chunk.append(repo)
            current_query = repo_query_part
            continue

        if (
            len(chunk) + 1 > max_repos_in_query
            or len(f"{current_query} OR {repo_query_part}") > max_search_string_len
        ):
            search_strings.append(current_query)
            chunk = [repo]
            current_query = repo_query_part
        else:
            chunk.append(repo)
            current_query = f"{current_query} OR {repo_query_part}"

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
        valid_repos = [repo for repo in search_result["items"] if repo["name"] in repos]
        logger.info(
            f"Found {len(valid_repos)} repositories for organization {organization}"
        )
        yield valid_repos


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


# sanitize .login fields containing [ or ] by replacing them with - when ingesting GitHub data.
def sanitize_login(login: str) -> str:
    return re.sub(
        r"\\[|\\](?=.)|\\]$", lambda m: "-" if m.group() != "]" else "", login
    )
