import os
from port_ocean.context.ocean import ocean
from gitlab_resync.group import resync_group
from gitlab_resync.merge_request import resync_merge_requests
from gitlab_resync.issues import resync_issues
from gitlab_resync.projects import resync_projects
from gitlab.webhooks import handle_gitlab_webhook
from aiohttp import web
import aiohttp
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve config from environment variables
integration_config = {
    "client_id": os.getenv("OCEAN__PORT__CLIENT_ID"),
    "client_secret": os.getenv("OCEAN__PORT__CLIENT_SECRET"),
    "base_url": os.getenv("OCEAN__PORT__BASE__URL"),
    "event_listener": os.getenv("OCEAN__EVENT__LISTENER"),
    "integration_identifier": os.getenv("OCEAN__INTEGRATION_IDENTIFIER"),
    "gitlab_token": os.getenv("GITLAB_TOKEN"),
    "gitlab_api_url": os.getenv("GITLAB_API_URL"),
    "rate_limit_max_retries": int(os.getenv("RATE_LIMIT_MAX_RETRIES", 5)),
    "webhook_url": os.getenv("WEBHOOK_URL"),
    "gitlab_project_id": os.getenv("GITLAB_PROJECT_ID")  # Ensure this is set in .env
}

# Function to set up webhook
async def setup_gitlab_webhook() -> None:
    gitlab_url = integration_config.get("gitlab_api_url")
    webhook_url = integration_config.get("webhook_url")
    project_id = integration_config.get("gitlab_project_id")

    # Check for valid GitLab project ID and webhook URL
    if not webhook_url:
        logger.warning("No webhook URL provided, skipping webhook creation.")
        return
    
    if not project_id:
        logger.error("No GitLab project ID provided, skipping webhook creation.")
        return

    logger.info(f"Setting up GitLab webhook for project ID: {project_id}")
    logger.info(f"Webhook URL: {webhook_url}")

    async with aiohttp.ClientSession() as session:
        # Register webhook in GitLab
        webhook_data = {
            "url": webhook_url,
            "push_events": True,
            "merge_requests_events": True,
            "issues_events": True
        }
        headers = {"PRIVATE-TOKEN": integration_config["gitlab_token"]}
        async with session.post(f"{gitlab_url}/projects/{project_id}/hooks", json=webhook_data, headers=headers) as resp:
            if resp.status == 201:
                logger.info("Webhook created successfully.")
            else:
                error_details = await resp.text()  # Get the response body for debugging
                logger.error(f"Failed to create webhook. Status: {resp.status}, Details: {error_details}")

# Webhook handling for GitLab events
async def handle_webhook(request) -> web.Response:
    logger.info("Request to /webhook started")  # Log when request starts
    data = await request.json()
    logger.info(f"Received webhook data: {data}")  # Log incoming webhook data
    try:
        await handle_gitlab_webhook(request)  # Pass the entire request for custom handling
        logger.info("Request to /webhook ended")  # Log when request ends
        return web.Response(status=200, text="Webhook received")
    except Exception as e:
        logger.error(f"Webhook handling error: {str(e)}")
        return web.Response(status=500, text=str(e))

# Resync handler for group
@ocean.on_resync('group')
async def resync_group_handler(kind: str):
    return await resync_group(kind)

# Resync handler for merge request
@ocean.on_resync('merge-request')
async def resync_merge_request_handler(kind: str):
    return await resync_merge_requests(kind)

# Resync handler for issues
@ocean.on_resync('issues')
async def resync_issues_handler(kind: str):
    return await resync_issues(kind)

# Resync handler for projects
@ocean.on_resync('projects')
async def resync_projects_handler(kind: str):
    return await resync_projects(kind)

# Optional: Listen to the start event of the integration
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitLab integration...")
    
    # Set up webhook during the integration start
    await setup_gitlab_webhook()

    logger.info("GitLab integration started.")

# Main entry point to run the aiohttp app for webhook handling
def start_webhook_listener():
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)  # Register the route for webhooks
    logger.info("Webhook route '/webhook' has been registered.")  # Log route registration

    web.run_app(app, host="0.0.0.0", port=8000)  # Ensure port matches your configuration

# Uncomment the following line to run the server
# if __name__ == '__main__':
#     start_webhook_listener()
