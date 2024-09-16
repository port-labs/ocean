import os
from aiohttp import web
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Retrieve GitLab secret token from environment variables
GITLAB_SECRET_TOKEN = os.getenv("GITLAB_SECRET_TOKEN")

async def handle_gitlab_webhook(request: web.Request) -> web.Response:
    """Handle incoming GitLab webhook events."""
    # Retrieve headers and body
    gitlab_token = request.headers.get('X-Gitlab-Token')
    
    if gitlab_token != GITLAB_SECRET_TOKEN:
        logger.warning(f"Forbidden request: invalid token {gitlab_token}")
        raise web.HTTPForbidden(text="Forbidden")

    event_type = request.headers.get('X-Gitlab-Event')
    payload = await request.json()

    logger.info(f"Received event type: {event_type}")

    # Route event to appropriate handler
    if event_type == "Merge Request Hook":
        await process_merge_request(payload)
    elif event_type == "Issue Hook":
        await process_issue(payload)
    elif event_type == "Push Hook":
        await process_push(payload)
    elif event_type == "Tag Push Hook":
        await process_tag_push(payload)
    else:
        logger.error(f"Unsupported event type: {event_type}")
        raise web.HTTPBadRequest(text="Unsupported event type")

    return web.Response(text="Event received")

async def process_merge_request(payload: dict) -> None:
    """Process GitLab merge request events."""
    # Add logic to handle merge request events
    logger.info(f"Processing Merge Request: {payload}")
    # Your merge request processing logic here

async def process_issue(payload: dict) -> None:
    """Process GitLab issue events."""
    # Add logic to handle issue events
    logger.info(f"Processing Issue: {payload}")
    # Your issue processing logic here

async def process_push(payload: dict) -> None:
    """Process GitLab push events."""
    # Add logic to handle push events
    logger.info(f"Processing Push: {payload}")
    # Your push processing logic here

async def process_tag_push(payload: dict) -> None:
    """Process GitLab tag push events."""
    # Add logic to handle tag push events
    logger.info(f"Processing Tag Push: {payload}")
    # Your tag push processing logic here
