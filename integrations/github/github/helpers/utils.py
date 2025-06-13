from enum import StrEnum
from typing import Any, Dict


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    """Enum for GitHub resource kinds."""

    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    RELEASE = "release"
    TAG = "tag"
    BRANCH = "branch"
    ENVIRONMENT = "environment"
    DEPLOYMENT = "deployment"


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
