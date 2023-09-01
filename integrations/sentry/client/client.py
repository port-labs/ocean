import httpx
from typing import Any
from rich.console import Console

console = Console()


class SentryClient:
    def __init__(self, sentry_base_url, auth_token) -> None:
        self.sentry_base_url = sentry_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": "Bearer " + f"{self.auth_token}"}
        console.print(f"Initializing Sentry client with {self.base_headers}")

        self.api_url = f"{self.sentry_base_url}/api/0"

        self.client = httpx.AsyncClient(headers=self.base_headers)

    async def get_paginated_projects(
        self,
    ) -> dict[str, Any]:
        project_response = await self.client.get(f"{self.api_url}/projects/")
        project_response.raise_for_status()
        return project_response.json()

    async def get_paginated_organizations(
        self,
    ) -> dict[str, Any]:
        organization_response = await self.client.get(f"{self.api_url}/organizations/")
        organization_response.raise_for_status()
        return organization_response.json()

    async def get_paginated_issues(
        self,
        organization_slug: str,
        project_slug: str,
    ) -> dict[str, Any]:
        issue_response = await self.client.get(
            f"{self.api_url}/projects/{organization_slug}/{project_slug}/issues/"
        )
        issue_response.raise_for_status()
        return issue_response.json()
