from port_ocean.context.ocean import ocean
from typing import List, Dict
from client import GitLabHandler
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize GitLabHandler
gitlab_handler = GitLabHandler()

# Listen to the resync event for the specified kinds
@ocean.on_resync()
async def on_resync(kind: str) -> List[Dict]:
    """
    Resync handler based on entity kind. Supports project, group, merge_request, and issue kinds.
    """
    if kind == "project":
        logging.info("Resyncing projects from GitLab...")
        return await gitlab_handler.fetch_projects()
    elif kind == "group":
        logging.info("Resyncing groups from GitLab...")
        return await gitlab_handler.fetch_groups()
    elif kind == "merge_request":
        logging.info("Resyncing merge requests from GitLab...")
        return await gitlab_handler.fetch_merge_requests()
    elif kind == "issue":
        logging.info("Resyncing issues from GitLab...")
        return await gitlab_handler.fetch_issues()
    
    logging.warning(f"Unsupported kind for resync: {kind}")
    return []

# Listen to the start event to set up webhooks
@ocean.on_start()
async def on_start() -> None:
    """
    Handler for integration start event.
    Sets up necessary configurations like webhook subscriptions.
    """
    logging.info("Starting GitLab integration and setting up webhooks...")
    await gitlab_handler.setup_webhook()
