from wcmatch import glob
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
from port_ocean.utils.cache import cache_coroutine_result


if TYPE_CHECKING:
    from github.clients.http.base_client import AbstractGithubClient
    from github.clients.http.graphql_client import GithubGraphQLClient


BASE_GLOB_FLAGS = glob.GLOBSTAR | glob.IGNORECASE


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
    DEPLOYMENT_STATUS = "deployment-status"
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
    response: Dict[str, Any],
    repo_name: str,
    key: str = "__repository",
    repo: Optional[dict[str, Any]] = None,
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
    if repo:
        response["__repository_object"] = repo
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
    if not response:
        logger.warning(
            f"No commit diff found for {before_sha}...{after_sha} in {repo_name} from {organization}"
        )
        return {"files": []}

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


@cache.cache_coroutine_result()
async def enrich_user_with_primary_email(
    client: "AbstractGithubClient", user: Dict[str, Any]
) -> Dict[str, Any]:
    response = await client.make_request(f"{client.base_url}/user/emails")
    data: list[dict[str, Any]] = response.json()
    if not data:
        logger.error("Failed to fetch user emails")
        return user

    primary_email = next((item for item in data if item["primary"] is True), None)
    if primary_email:
        user["email"] = primary_email["email"]
    return user


def issue_matches_labels(
    issue_labels: list[dict[str, Any]], required_labels: Optional[list[str]]
) -> bool:
    """
    Check if an issue's labels match the required labels filter.

    Args:
        issue_labels: List of label objects from webhook payload
        required_labels: List of required labels

    Returns:
        True if issue matches (has ALL of the required labels), False otherwise
    """
    if not required_labels:
        return True

    required_set = {label.lower() for label in required_labels}
    if not required_set:
        return True

    issue_label_names = {label["name"].lower() for label in issue_labels}

    return required_set.issubset(issue_label_names)


def has_exhausted_rate_limit_headers(headers: Any) -> bool:
    """
    Return True when GitHub's rate limit headers indicate an exhausted quota.

    Accepts any headers-like mapping (e.g. `httpx.Headers`, `dict[str, str]`).
    """

    return (
        headers.get("x-ratelimit-remaining") == "0"
        and headers.get("x-ratelimit-reset") is not None
    )


def matches_glob_pattern(path: str, pattern: str, flags: int = 0) -> bool:
    combined_flags = BASE_GLOB_FLAGS | flags
    return glob.globmatch(path, pattern, flags=combined_flags)


@cache_coroutine_result()
async def get_saml_identities(
    client: "GithubGraphQLClient", organization: str
) -> dict[str, str]:
    """Fetch and cache SAML identities for an organization.

    Returns a mapping of GitHub login -> SAML nameId (email).
    """
    from github.helpers.gql_queries import LIST_EXTERNAL_IDENTITIES_GQL

    variables = {
        "organization": organization,
        "first": 100,
        "__path": "organization.samlIdentityProvider.externalIdentities",
        "__node_key": "edges",
    }

    saml_users: dict[str, str] = {}

    logger.info(f"Starting SAML identity fetch for organization '{organization}'")

    try:
        async for identity_batch in client.send_paginated_request(
            LIST_EXTERNAL_IDENTITIES_GQL,
            variables,
        ):
            for user in identity_batch:
                if user["node"].get("user"):
                    login = user["node"]["user"]["login"]
                    name_id = user["node"]["samlIdentity"]["nameId"]
                    saml_users[login] = name_id

        logger.info(
            f"SAML fetch complete for '{organization}': {len(saml_users)} identities"
        )
    except TypeError:
        logger.info(f"SAML not enabled for organization '{organization}'")

    return saml_users


async def enrich_members_with_saml_email(
    client: "GithubGraphQLClient",
    organization: str,
    members: list[dict[str, Any]],
) -> None:
    """Enrich members in-place with SAML email where email is missing."""
    members_without_email = [m for m in members if not m.get("email")]
    if not members_without_email:
        return

    logger.info(
        f"Found {len(members_without_email)} members without email, "
        f"fetching from SAML for organization '{organization}'"
    )
    saml_users = await get_saml_identities(client, organization)

    enriched = 0
    for member in members_without_email:
        if member["login"] in saml_users:
            member["email"] = saml_users[member["login"]]
            enriched += 1

    logger.info(
        f"Enriched {enriched}/{len(members_without_email)} members with SAML email "
        f"for organization '{organization}'"
    )
