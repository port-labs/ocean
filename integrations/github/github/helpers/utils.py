from enum import StrEnum
from typing import Any, Dict, List, Set, Tuple
from github.clients.http.base_client import AbstractGithubClient
from loguru import logger


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    """Enum for GitHub resource kinds."""

    REPOSITORY = "repository"
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


def extract_repo_params(params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract the repository name and other parameters from the options."""
    repo_name = params.pop("repo_name")
    return repo_name, params


async def fetch_commit_diff(
    client: AbstractGithubClient, repo_name: str, before_sha: str, after_sha: str
) -> Dict[str, Any]:
    """
    Fetch the commit comparison data from GitHub API.
    """
    resource = f"{client.base_url}/repos/{client.organization}/{repo_name}/compare/{before_sha}...{after_sha}"
    response = await client.send_api_request(resource)

    logger.info(f"Found {len(response['files'])} files in commit diff")

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
