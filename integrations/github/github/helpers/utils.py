from enum import StrEnum
from typing import (
    Any,
    Dict,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    TYPE_CHECKING,
)

from loguru import logger

from port_ocean.utils import cache


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


def enrich_with_organization(
    response: Dict[str, Any], organization: str
) -> Dict[str, Any]:
    """Helper function to enrich response with organization information.
    Args:
        response: The response to enrich
        organization: The name of the organization
    Returns:
        The enriched response
    """
    return {**response, "__organization": organization}


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


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


@cache.cache_coroutine_result()
async def get_repository_metadata(
    client: "AbstractGithubClient", organization: str, repo_name: str
) -> Dict[str, Any]:
    url = f"{client.base_url}/repos/{organization}/{repo_name}"
    logger.info(f"Fetching metadata for repository: {repo_name} from {organization}")
    return await client.send_api_request(url)
