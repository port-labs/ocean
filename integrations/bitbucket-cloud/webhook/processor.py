from loguru import logger

from port_ocean.context.ocean import ocean
from typing import Any, Dict


def clean_uuid(uuid_str: str) -> str:
    """Remove curly braces from a UUID string."""
    return uuid_str.strip("{}")

async def process_repo_push_event(event: Dict[str, Any]) -> None:
    """
    Process a repository push event.

    Extracts repository information from the event payload and updates the corresponding entity.

    Args:
        event (Dict[str, Any]): The event payload containing repository data.
    """
    repo: Dict[str, Any] = event["repository"]
    repo_name: str = repo.get("name", "Unknown Repository")
    logger.info(f"Processing push event for repository: {repo_name}")

    entity: Dict[str, Any] = {
        "identifier": clean_uuid(repo["uuid"]),
        "title": repo_name,
        "blueprint": "bitbucketRepository",
        "properties": {
            "url": repo["links"]["html"]["href"],
            "scm": repo.get("scm"),
            "language": repo.get("language"),
            "description": repo.get("description"),
        },
        "relations": {
            "project": repo["project"]["key"],
        },
    }

    await ocean.update_entities([entity])

async def process_pull_request_event(event: Dict[str, Any]) -> None:
    """
    Process a pull request created event.

    Extracts pull request and repository information from the event payload and updates the corresponding entity.

    Args:
        event (Dict[str, Any]): The event payload containing pull request and repository data.
    """
    pr: Dict[str, Any] = event["pullrequest"]
    repo: Dict[str, Any] = event["repository"]
    pr_id = pr.get("id")
    pr_title = pr.get("title", "No Title")
    logger.info(f"Processing pull request event: PR #{pr_id} - {pr_title}")

    entity: Dict[str, Any] = {
        "identifier": pr_id,
        "title": pr_title,
        "blueprint": "bitbucketPullRequest",
        "properties": {
            "state": pr.get("state"),
            "author": pr["author"]["display_name"],
        },
        "relations": {
            "repository": clean_uuid(repo["uuid"]),
        },
    }

    await ocean.update_entities([entity])
