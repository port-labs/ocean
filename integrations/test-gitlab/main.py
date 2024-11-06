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
    Resync handler based on entity kind. Supports only 'group' kind in this branch.
    """
    if kind == "group":
        logging.info("Resyncing groups from GitLab...")
        return await gitlab_handler.fetch_groups()
    
    logging.warning(f"Unsupported kind for resync: {kind}")
    return []
