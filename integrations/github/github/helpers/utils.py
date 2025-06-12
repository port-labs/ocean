from enum import StrEnum
from typing import Any, Dict, List, Set, Tuple
from github.clients.http.base_client import AbstractGithubClient
from loguru import logger


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    WORKFLOW = "workflow"
    WORKFLOW_RUN = "workflow-run"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"


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


def _extract_changed_files(
    files: List[Dict[str, Any]]
) -> Tuple[Set[Dict[str, Any]], Set[Dict[str, Any]]]:
    """
    Extract files that were changed in the push event.
    Returns a set of file paths that were added, modified, or removed.
    """
    deleted_files: Set[Dict[str, Any]] = set()
    updated_files: Set[Dict[str, Any]] = set()

    for file in files:
        (deleted_files if file.get("status") == "removed" else updated_files).append(
            file
        )

    return deleted_files, updated_files
