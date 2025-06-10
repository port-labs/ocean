from enum import StrEnum
from typing import Any, Dict


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"


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
