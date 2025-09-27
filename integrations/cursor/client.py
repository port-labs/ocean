from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator
from urllib.parse import urljoin

import httpx
from loguru import logger

from port_ocean.helpers.async_client import OceanAsyncClient


class CursorClient:
    """Cursor API client for fetching utilization data."""

    BASE_URL = "https://api.cursor.com"

    def __init__(self, api_key: str):
        """Initialize Cursor client with API key."""
        self.api_key = api_key
        self.auth = httpx.BasicAuth(api_key, "")

        # Initialize async HTTP client with retry configuration
        self.client = OceanAsyncClient()

    async def _make_request(
        self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Cursor API."""
        url = urljoin(self.BASE_URL, endpoint)

        headers = {"Content-Type": "application/json"}

        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=headers, auth=self.auth)
            elif method.upper() == "POST":
                response = await self.client.post(
                    url, headers=headers, auth=self.auth, json=data or {}
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

    async def get_team_members(self) -> List[Dict[str, Any]]:
        """Get list of team members."""
        endpoint = "/teams/members"
        response = await self._make_request(endpoint)
        return response.get("teamMembers", [])

    async def get_daily_usage_data(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get daily usage metrics."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        endpoint = "/teams/daily-usage-data"
        data = {
            "startDate": int(
                start_date.timestamp() * 1000
            ),  # Convert to epoch milliseconds
            "endDate": int(end_date.timestamp() * 1000),
        }

        response = await self._make_request(endpoint, method="POST", data=data)
        yield response.get("data", [])

    async def get_filtered_usage_events(
        self,
        start_date: datetime,
        end_date: datetime,
        page: int = 1,
        page_size: int = 100,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        endpoint = "/teams/filtered-usage-events"
        data: Dict[str, Any] = {
            "startDate": int(start_date.timestamp() * 1000),
            "endDate": int(end_date.timestamp() * 1000),
            "page": page,
            "pageSize": page_size,
        }
        response = await self._make_request(endpoint, method="POST", data=data)

        events = response.get("usageEvents", [])
        yield events

        pagination = response.get("pagination", {})
        if pagination.get("hasNextPage", False):
            current_page = pagination.get("currentPage", 1)
            next_page = current_page + 1
            async for more_events in self.get_filtered_usage_events(
                start_date, end_date, next_page, page_size
            ):
                yield more_events

    async def get_filtered_user_usage(
        self, start_date: datetime, end_date: datetime
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        async for events_batch in self.get_filtered_usage_events(
            start_date,
            end_date,
        ):
            yield events_batch

    async def get_blocklisted_repos(self) -> List[Dict[str, Any]]:
        endpoint = "/teams/repo-blocklists"
        response = await self._make_request(endpoint)
        return response.get("repositories", [])

    async def get_spending_data(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get spending data for the team."""
        endpoint = "/teams/spending"
        params = {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}

        from urllib.parse import urlencode

        url = f"{self.BASE_URL}{endpoint}?{urlencode(params)}"

        response = await self.client.get(url, auth=self.auth)
        response.raise_for_status()
        return response.json()

    async def get_ai_commit_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        page: int = 1,
        page_size: int = 100,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get AI commit metrics with pagination."""
        endpoint = "/analytics/ai-code/commits"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "page": page,
            "pageSize": page_size,
        }

        from urllib.parse import urlencode

        url = f"{self.BASE_URL}{endpoint}?{urlencode(params)}"

        response = await self.client.get(url, auth=self.auth)
        response.raise_for_status()
        data = response.json()

        yield data.get("items", [])

        total_count = data.get("totalCount", 0)
        current_page = data.get("page", 1)
        page_size = data.get("pageSize", 100)

        if current_page * page_size < total_count:
            async for more_items in self.get_ai_commit_metrics(
                start_date,
                end_date,
                current_page + 1,
                page_size,
            ):
                yield more_items

    async def get_ai_code_change_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        page: int = 1,
        page_size: int = 100,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get AI code change metrics with pagination."""
        endpoint = "/analytics/ai-code/changes"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "page": page,
            "pageSize": page_size,
        }

        # Add query parameters to URL"
        from urllib.parse import urlencode

        url = f"{self.BASE_URL}{endpoint}?{urlencode(params)}"

        response = await self.client.get(url, auth=self.auth)
        response.raise_for_status()
        data = response.json()

        yield data.get("items", [])

        # Handle pagination if there are more pages
        total_count = data.get("totalCount", 0)
        current_page = data.get("page", 1)
        page_size = data.get("pageSize", 100)

        if current_page * page_size < total_count:
            async for more_items in self.get_ai_code_change_metrics(
                start_date, end_date, current_page + 1, page_size
            ):
                yield more_items
