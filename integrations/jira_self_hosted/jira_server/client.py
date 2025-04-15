# jira_server.py

from enum import StrEnum
from typing import Any, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 50


class ResourceKey(StrEnum):
    PROJECTS = "projects"
    ISSUES = "issues"


class JiraServerClient:
    def __init__(self, server_url: str, username: str, password: str) -> None:
        self.server_url = server_url
        self.api_url = f"{self.server_url}/rest/api/2"
        self.client = http_async_client
        self.client.auth = httpx.BasicAuth(username, password)

    async def get_projects(self, params: dict[str, Any] | None = None) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects from Jira Server with pagination."""
        logger.info("Getting projects from Jira Server")
        page = 0

        while True:
            request_params = {
                "maxResults": PAGE_SIZE,
                "startAt": page * PAGE_SIZE,
                **(params or {})
            }

            response = await self.client.get(f"{self.api_url}/project", params=request_params)
            response.raise_for_status()
            projects = response.json()

            if not projects:
                break

            yield projects

            if len(projects) < PAGE_SIZE:
                break

            page += 1

    async def get_issues(self, params: dict[str, Any] | None = None) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all issues from Jira Server with pagination."""
        logger.info("Getting issues from Jira Server")
        if params and "jql" in params:
            logger.info(f"Using JQL filter: {params['jql']}")

        page = 0

        while True:
            request_params = {
                "maxResults": PAGE_SIZE,
                "startAt": page * PAGE_SIZE,
                **(params or {})
            }

            response = await self.client.get(f"{self.api_url}/search", params=request_params)
            response.raise_for_status()
            data = response.json()
            issues = data.get("issues", [])

            if not issues:
                break

            yield issues

            if len(issues) < PAGE_SIZE:
                break

            page += 1

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        """Get a single project by its key."""
        response = await self.client.get(f"{self.api_url}/project/{project_key}")
        response.raise_for_status()
        return response.json()

    async def get_single_issue(self, issue_key: str) -> dict[str, Any]:
        """Get a single issue by its key."""
        response = await self.client.get(f"{self.api_url}/issue/{issue_key}")
        response.raise_for_status()
        return response.json()

    async def get_single_user(self, username: str) -> dict[str, Any]:
        """
        Get a single user from Jira Server by username.
        Jira Server’s API requires 'username' (legacy identifier) rather than 'accountId'.
        """
        response = await self.client.get(f"{self.api_url}/user", params={"username": username})
        response.raise_for_status()
        return response.json()

    async def get_users(self, username: str = "") -> list[dict[str, Any]]:
        """
        Get users from Jira Server.
        If a username is provided, the results are filtered by that username.
        Otherwise, the endpoint should return a default set of users.
        Note: This does not implement custom pagination.
        """
        response = await self.client.get(f"{self.api_url}/user/search?username=")
        response.raise_for_status()
        return response.json()
