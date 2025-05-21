import httpx
from loguru import logger
import asyncio

class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.client = httpx.AsyncClient()

    def _headers(self):
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json"
        }

    async def close(self):
        await self.client.aclose()

    async def _get_paginated(self, url: str, retries: int = 3, backoff: float = 1.0):
        results = []
        while url:
            logger.info(f"Fetching: {url}")
            for attempt in range(retries):
                try:
                    response = await self.client.get(url, headers=self._headers(), timeout=10)

                    if response.status_code == 429:
                        logger.warning("Rate limit hit. Retrying...")
                        await asyncio.sleep(backoff * (attempt + 1))
                        continue

                    if response.status_code >= 400:
                        text = response.text
                        logger.error(f"GitHub API error {response.status_code}: {text}")
                        return results

                    data = response.json()
                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict):
                        results.extend(data.get("items", []))

                    # Handle pagination
                    link_header = response.headers.get("link")
                    next_url = None
                    if link_header:
                        for part in link_header.split(","):
                            if 'rel="next"' in part:
                                next_url = part.split(";")[0].strip()[1:-1]
                                break

                    url = next_url
                    break
                except Exception as e:
                    logger.error(f"Request to {url} failed: {str(e)}")
                    await asyncio.sleep(backoff * (attempt + 1))
            else:
                logger.error(f"Failed to fetch {url} after {retries} retries")
                break

        return results

    async def get_repositories(self, org: str):
        return await self._get_paginated(f"{self.base_url}/orgs/{org}/repos")

    async def get_issues(self, org: str, repo: str):
        return await self._get_paginated(f"{self.base_url}/repos/{org}/{repo}/issues")

    async def get_pull_requests(self, org: str, repo: str):
        return await self._get_paginated(f"{self.base_url}/repos/{org}/{repo}/pulls")

    async def get_workflows(self, org: str, repo: str):
        data = await self._get_paginated(f"{self.base_url}/repos/{org}/{repo}/actions/workflows")
        return data if isinstance(data, list) else data.get("workflows", [])

    async def get_teams(self, org: str):
        return await self._get_paginated(f"{self.base_url}/orgs/{org}/teams")