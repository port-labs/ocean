from loguru import logger

from port_ocean.context.ocean import ocean

async def process_repo_push_event(event: dict) -> None:
    """Process a repo:push event."""
    repo = event["repository"]
    logger.info(f"Processing push event for repository: {repo['name']}")

    entity = {
        "identifier": repo["uuid"][1:-1],
        "title": repo["name"],
        "blueprint": "bitbucketRepository",
        "properties": {
            "url": repo["links"]["html"]["href"],
            "scm": repo["scm"],
            "language": repo["language"],
            "description": repo["description"],
        },
        "relations": {
            "project": repo["project"]["key"],
        },
    }

    await ocean.update_entities([entity])

async def process_pull_request_event(event: dict) -> None:
    """Process a pullrequest:created event."""
    pr = event["pullrequest"]
    repo = event["repository"]
    logger.info(f"Processing pull request event: PR #{pr['id']} - {pr['title']}")

    entity = {
        "identifier": pr["id"],
        "title": pr["title"],
        "blueprint": "bitbucketPullRequest",
        "properties": {
            "state": pr["state"],
            "author": pr["author"]["display_name"],
        },
        "relations": {
            "repository": repo["uuid"][1:-1],  # Remove curly braces from UUID
        },
    }
    await ocean.update_entities([entity])