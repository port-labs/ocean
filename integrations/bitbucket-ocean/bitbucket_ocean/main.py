import asyncio
import logging
import yaml
from ocean.async_client import OceanAsyncClient
from ocean.integration import OceanIntegration
from ocean.webhook import WebhookHandler
from ocean.exceptions import RateLimitExceededError, OceanError

# Load configuration
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"
WORKSPACE = config["bitbucket"]["workspace"]

class BitbucketOceanIntegration(OceanIntegration):
    def __init__(self, config):
        super().__init__(config)
        self.client = OceanAsyncClient(base_url=BITBUCKET_API_BASE, headers={
            "Authorization": f"Bearer {config['bitbucket']['access_token']}",
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

    async def _fetch_paginated_data(self, endpoint):
        """Handles API pagination and rate limits."""
        results = []
        url = endpoint
        while url:
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("values", []))
                url = data.get("next", None)
            except RateLimitExceededError:
                logging.warning("Rate limit exceeded, retrying after 10 seconds...")
                await asyncio.sleep(10)
            except OceanError as e:
                logging.error(f"API error: {e}")
                break
        return results

    async def ingest_data_to_port(self):
        """Fetch data from Bitbucket and push to Port."""
        try:
            projects = await self.fetch_projects()
            repositories = await self.fetch_repositories()
            pull_requests = [await self.fetch_pull_requests(repo["slug"]) for repo in repositories]

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
    integration = BitbucketOceanIntegration(config)
    asyncio.run(integration.ingest_data_to_port())
