import asyncio
import logging
import os
from dotenv import load_dotenv
from ocean.async_client import OceanAsyncClient
from ocean.integration import OceanIntegration
from ocean.webhook import WebhookHandler
from ocean.exceptions import RateLimitExceededError, OceanError

# Load environment variables
load_dotenv()

# Get API credentials from environment variables
BITBUCKET_ACCESS_TOKEN = os.getenv("BITBUCKET_ACCESS_TOKEN")
PORT_API_KEY = os.getenv("PORT_API_KEY")
WORKSPACE = os.getenv("BITBUCKET_WORKSPACE")

# Validate API credentials
if not BITBUCKET_ACCESS_TOKEN or not PORT_API_KEY or not WORKSPACE:
    raise ValueError("Missing required environment variables. Ensure BITBUCKET_ACCESS_TOKEN, BITBUCKET_WORKSPACE, and PORT_API_KEY are set.")

BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"


class BitbucketOceanIntegration(OceanIntegration):
    def __init__(self):
        super().__init__({"api_key": PORT_API_KEY})
        self.client = OceanAsyncClient(base_url=BITBUCKET_API_BASE, headers={
            "Authorization": f"Bearer {BITBUCKET_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        })

    async def fetch_projects(self):
        """Fetch all Bitbucket projects."""
        return await self._fetch_paginated_data(f"/teams/{WORKSPACE}/projects/")

    async def fetch_repositories(self):
        """Fetch all Bitbucket repositories."""
        return await self._fetch_paginated_data(f"/repositories/{WORKSPACE}")

    async def fetch_pull_requests(self, repo_slug):
        """Fetch PRs for a repository."""
        return await self._fetch_paginated_data(f"/repositories/{WORKSPACE}/{repo_slug}/pullrequests")

    async def _fetch_paginated_data(self, endpoint, max_retries=3):
        """Handles API pagination and retries on failure."""
        results = []
        url = endpoint
        retries = 0

        while url:
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("values", []))
                url = data.get("next", None)
                retries = 0  # Reset retries on success
            except RateLimitExceededError:
                logging.warning("Rate limit exceeded, retrying after 10 seconds...")
                await asyncio.sleep(10)
            except OceanError as e:
                retries += 1
                if retries >= max_retries:
                    logging.error(f"API error after {max_retries} retries: {e}")
                    break
                logging.warning(f"Temporary API error, retrying in 5 seconds... ({retries}/{max_retries})")
                await asyncio.sleep(5)
        return results

    async def ingest_data_to_port(self):
        """Fetch data from Bitbucket and push to Port."""
        try:
            projects = await self.fetch_projects()
            repositories = await self.fetch_repositories()

            # Fetch pull requests concurrently using asyncio.gather()
            pull_requests = await asyncio.gather(
                *[self.fetch_pull_requests(repo["slug"]) for repo in repositories]
            )

            await self.port_client.ingest("bitbucket_projects", projects)
            await self.port_client.ingest("bitbucket_repositories", repositories)
            await self.port_client.ingest("bitbucket_pull_requests", pull_requests)
        except Exception as e:
            logging.error(f"Failed to ingest data: {e}")


class BitbucketWebhook(WebhookHandler):
    async def handle_event(self, event):
        """Handle real-time webhook events."""
        logging.info(f"Webhook event received: {event}")


if __name__ == "__main__":
    integration = BitbucketOceanIntegration()
    asyncio.run(integration.ingest_data_to_port())
