import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

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
        url = f'{self.base_url}/rate_limit'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            rate_limit = response.json()
            logger.info('Rate Limit: %s', rate_limit)
            return rate_limit
        else:
            response.raise_for_status()

    async def get_repositories(self):
        await self.check_rate_limit()
        url = f'{self.base_url}/user/repos'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    async def get_issues(self, username: str, repo: str):
        await self.check_rate_limit()
        url = f'{self.base_url}/repos/{username}/{repo}/issues'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    async def get_pull_requests(self, username: str, repo: str):
        await self.check_rate_limit()
        url = f'{self.base_url}/repos/{username}/{repo}/pulls'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    async def get_organizations(self):
        await self.check_rate_limit()
        url = f'{self.base_url}/user/orgs'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    async def get_teams(self, org: str):
        await self.check_rate_limit()
        url = f'{self.base_url}/orgs/{org}/teams'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    async def get_workflows(self, username: str, repo: str):
        await self.check_rate_limit()
        url = f'{self.base_url}/repos/{username}/{repo}/actions/workflows'
        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()