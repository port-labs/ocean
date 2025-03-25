import logging
import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GithubHandler:
    def __init__(self) -> None:
        self.token = ocean.integration_config["github_access_token"]
        self.base_url = ocean.integration_config["github_base_url"]
        self.client = http_async_client
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github+json'
        }

    async def check_rate_limit(self):
        """Check the API rate limit and handle retries if necessary."""
        url = f'{self.base_url}/rate_limit'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            rate_limit = response.json()
            logger.info('Rate Limit: %s', rate_limit)
            return rate_limit
        else:
            response.raise_for_status()

    async def fetch_with_retry(self, url: str, retries: int = 3, backoff_factor: int = 2):
        """Fetch data with retry logic for handling rate limits."""
        for attempt in range(retries):
            response = await self.client.get(url, headers=self.headers)
            match response.status_code:
                case 200:
                    return response.json()
                case 429:  # Rate limit exceeded
                    retry_after = int(response.headers.get("Retry-After", backoff_factor))
                    logger.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after * (backoff_factor ** attempt))
                case _:
                    response.raise_for_status()
        raise Exception("Max retries exceeded")

    @cache_iterator_result()
    async def get_repositories(self):
        """Fetch all repositories for the authenticated user."""
        url = f'{self.base_url}/user/repos'
        data = await self.fetch_with_retry(url)
        for repo in data:
            yield repo

    @cache_iterator_result()
    async def get_issues(self, username: str, repo: str):
        """Fetch all issues for a specific repository."""
        url = f'{self.base_url}/repos/{username}/{repo}/issues'
        data = await self.fetch_with_retry(url)
        for issue in data:
            yield issue

    @cache_iterator_result()
    async def get_pull_requests(self, username: str, repo: str):
        """Fetch all pull requests for a specific repository."""
        url = f'{self.base_url}/repos/{username}/{repo}/pulls'
        data = await self.fetch_with_retry(url)
        for pull_request in data:
            yield pull_request

    @cache_iterator_result()
    async def get_organizations(self):
        """Fetch all organizations the authenticated user belongs to."""
        url = f'{self.base_url}/user/orgs'
        data = await self.fetch_with_retry(url)
        for org in data:
            yield org

    @cache_iterator_result()
    async def get_teams(self, org: str):
        """Fetch all teams for a specific organization."""
        url = f'{self.base_url}/orgs/{org}/teams'
        data = await self.fetch_with_retry(url)
        for team in data:
            yield team

    @cache_iterator_result()
    async def get_workflows(self, username: str, repo: str):
        """Fetch all workflows for a specific repository."""
        url = f'{self.base_url}/repos/{username}/{repo}/actions/workflows'
        data = await self.fetch_with_retry(url)
        for workflow in data:
            yield workflow