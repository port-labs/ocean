import asyncio
import httpx
from typing import Any, Dict, List, AsyncGenerator, Optional
from loguru import logger
from port_ocean.utils.async_http import create_http_session


class OktaClient:
    """Okta API client for fetching users, groups, roles, permissions, and applications"""
    
    def __init__(self, domain: str, api_token: str):
        self.domain = domain.rstrip('/')
        if not self.domain.startswith('https://'):
            self.domain = f"https://{self.domain}"
        
        self.api_token = api_token
        self.base_url = f"{self.domain}/api/v1"
        self.headers = {
            "Authorization": f"SSWS {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to Okta API"""
        url = f"{self.base_url}{endpoint}"
        
        async with create_http_session() as session:
            response = await session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
    
    async def _get_paginated_data(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get paginated data from Okta API"""
        if params is None:
            params = {}
        
        # Default limit if not specified
        if "limit" not in params:
            params["limit"] = 200
            
        url = f"{self.base_url}{endpoint}"
        
        async with create_http_session() as session:
            while url:
                logger.debug(f"Fetching data from: {url}")
                response = await session.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                if data:
                    yield data
                
                # Get next page URL from Link header
                link_header = response.headers.get("Link", "")
                next_url = None
                if link_header:
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link:
                            next_url = link.split(">")[0].strip("<")
                            break
                
                url = next_url
                params = None  # Clear params for subsequent requests since they're in the URL
    
    async def get_paginated_users(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get paginated users from Okta"""
        async for users in self._get_paginated_data("/users", params):
            yield users
    
    async def get_paginated_groups(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get paginated groups from Okta"""
        async for groups in self._get_paginated_data("/groups", params):
            yield groups
    
    async def get_paginated_roles(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get paginated roles from Okta"""
        # Roles in Okta are typically admin roles
        async for roles in self._get_paginated_data("/iam/roles", params):
            yield roles
    
    async def get_paginated_permissions(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get paginated permissions (role assignments) from Okta"""
        # Role assignments can be fetched per user or as a global view
        async for permissions in self._get_paginated_data("/iam/roleAssignments", params):
            yield permissions
    
    async def get_paginated_applications(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get paginated applications from Okta"""
        async for applications in self._get_paginated_data("/apps", params):
            yield applications
    
    async def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """Get roles assigned to a specific user"""
        try:
            data = await self._make_request(f"/users/{user_id}/roles")
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch roles for user {user_id}: {e}")
            return []
    
    async def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """Get groups for a specific user"""
        try:
            data = await self._make_request(f"/users/{user_id}/groups")
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch groups for user {user_id}: {e}")
            return []
    
    async def get_group_users(self, group_id: str) -> List[Dict[str, Any]]:
        """Get users in a specific group"""
        try:
            data = await self._make_request(f"/groups/{group_id}/users")
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch users for group {group_id}: {e}")
            return []
    
    async def enrich_groups_with_members(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich groups with their members"""
        enriched_groups = []
        
        for group in groups:
            group_id = group.get("id")
            if group_id:
                try:
                    members = await self.get_group_users(group_id)
                    group["members"] = members
                except Exception as e:
                    logger.warning(f"Failed to enrich group {group_id} with members: {e}")
                    group["members"] = []
            
            enriched_groups.append(group)
        
        return enriched_groups
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get detailed profile for a specific user"""
        try:
            return await self._make_request(f"/users/{user_id}")
        except Exception as e:
            logger.error(f"Failed to fetch profile for user {user_id}: {e}")
            return {}
    
    async def get_group_profile(self, group_id: str) -> Dict[str, Any]:
        """Get detailed profile for a specific group"""
        try:
            return await self._make_request(f"/groups/{group_id}")
        except Exception as e:
            logger.error(f"Failed to fetch profile for group {group_id}: {e}")
            return {}