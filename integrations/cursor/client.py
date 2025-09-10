import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator
from urllib.parse import urljoin

import httpx
from loguru import logger

from port_ocean.utils.async_http import AsyncHTTPClient


class CursorClient:
    """Cursor API client for fetching utilization data."""
    
    BASE_URL = "https://api.cursor.com"
    
    def __init__(self, api_key: str, team_id: str):
        """Initialize Cursor client with API key and team ID."""
        self.api_key = api_key
        self.team_id = team_id
        self.auth = httpx.BasicAuth(api_key, "")
        
        # Initialize async HTTP client with retry configuration
        self.client = AsyncHTTPClient(
            timeout=30,
            max_retries=5,
            retry_delay=1.0,
        )
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated request to Cursor API."""
        url = urljoin(self.BASE_URL, endpoint)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} fetching {url}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise
    
    async def get_team_members(self) -> List[Dict[str, Any]]:
        """Get list of team members."""
        endpoint = f"/api/v1/teams/{self.team_id}/members"
        return await self._make_request(endpoint)
    
    async def get_daily_usage_data(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get daily usage metrics."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        endpoint = f"/api/v1/teams/{self.team_id}/usage/daily"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        data = await self._make_request(endpoint, params)
        
        # Handle pagination if present
        if isinstance(data, list):
            yield data
        elif isinstance(data, dict) and "data" in data:
            yield data["data"]
            
            # Handle pagination
            while data.get("next_page_token"):
                params["page_token"] = data["next_page_token"]
                data = await self._make_request(endpoint, params)
                if "data" in data:
                    yield data["data"]
                else:
                    break
    
    async def get_filtered_usage_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_email: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get filtered usage events."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
        
        endpoint = f"/api/v1/teams/{self.team_id}/events"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        if user_email:
            params["user"] = user_email
        
        data = await self._make_request(endpoint, params)
        
        # Handle pagination
        if isinstance(data, list):
            yield data
        elif isinstance(data, dict) and "events" in data:
            yield data["events"]
            
            while data.get("next_page_token"):
                params["page_token"] = data["next_page_token"]
                data = await self._make_request(endpoint, params)
                if "events" in data:
                    yield data["events"]
                else:
                    break
    
    async def get_ai_commit_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format_type: str = "json"
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get AI commit metrics."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        endpoint = f"/api/v1/teams/{self.team_id}/ai/commits"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "format": format_type
        }
        
        data = await self._make_request(endpoint, params)
        
        if isinstance(data, list):
            yield data
        elif isinstance(data, dict) and "commits" in data:
            yield data["commits"]
            
            while data.get("next_page_token"):
                params["page_token"] = data["next_page_token"]
                data = await self._make_request(endpoint, params)
                if "commits" in data:
                    yield data["commits"]
                else:
                    break
    
    async def get_ai_code_changes(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get AI code change metrics."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        endpoint = f"/api/v1/teams/{self.team_id}/ai/code-changes"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        data = await self._make_request(endpoint, params)
        
        if isinstance(data, list):
            yield data
        elif isinstance(data, dict) and "changes" in data:
            yield data["changes"]
            
            while data.get("next_page_token"):
                params["page_token"] = data["next_page_token"]
                data = await self._make_request(endpoint, params)
                if "changes" in data:
                    yield data["changes"]
                else:
                    break
    
    async def get_team_info(self) -> Dict[str, Any]:
        """Get team information."""
        endpoint = f"/api/v1/teams/{self.team_id}"
        return await self._make_request(endpoint)
    
    async def get_user_daily_usage(
        self,
        user_email: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get daily usage for a specific user."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        endpoint = f"/api/v1/teams/{self.team_id}/users/{user_email}/usage"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        data = await self._make_request(endpoint, params)
        
        if isinstance(data, list):
            yield data
        elif isinstance(data, dict) and "usage" in data:
            yield data["usage"]
            
            while data.get("next_page_token"):
                params["page_token"] = data["next_page_token"]
                data = await self._make_request(endpoint, params)
                if "usage" in data:
                    yield data["usage"]
                else:
                    break
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.close()