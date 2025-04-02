from typing import Any, Dict
import asyncio
from loguru import logger
from httpx import HTTPStatusError

from github_cloud.helpers.exceptions import ResourceNotFoundError, InvalidResourceTypeError
from github_cloud.models.resource import ResourceType, ResourceEndpoint
from github_cloud.types import GithubClientProtocol

class ResourceManager:
    """Manages GitHub resource operations with improved error handling and validation."""
    
    def __init__(self, client: GithubClientProtocol):
        self.client = client
        self.base_url = client.base_url
        self.organization = client.organization
        self._endpoints = self._initialize_endpoints()

    def _initialize_endpoints(self) -> Dict[ResourceType, ResourceEndpoint]:
        """Initialize the mapping of resource types to their endpoint configurations."""
        return {
            ResourceType.REPOSITORY: ResourceEndpoint(
                path_template="repos/{organization}/{identifier}",
                requires_organization=True
            ),
            ResourceType.PULL_REQUEST: ResourceEndpoint(
                path_template="repos/{organization}/{identifier}/pulls/{pr_number}",
                requires_organization=True
            ),
            ResourceType.ISSUE: ResourceEndpoint(
                path_template="repos/{organization}/{identifier}/issues/{issue_number}",
                requires_organization=True
            ),
            ResourceType.TEAM: ResourceEndpoint(
                path_template="orgs/{organization}/teams/{identifier}",
                requires_organization=True
            ),
            ResourceType.WORKFLOW: ResourceEndpoint(
                path_template="repos/{organization}/{identifier}/actions/workflows/{workflow_id}",
                requires_organization=True
            ),
            ResourceType.USER: ResourceEndpoint(
                path_template="users/{identifier}",
                requires_organization=False
            ),
            ResourceType.ORGANIZATION: ResourceEndpoint(
                path_template="orgs/{identifier}",
                requires_organization=False
            ),
            ResourceType.BRANCH: ResourceEndpoint(
                path_template="repos/{organization}/{identifier}/branches/{branch_name}",
                requires_organization=True
            ),
            ResourceType.COMMIT: ResourceEndpoint(
                path_template="repos/{organization}/{identifier}/commits/{sha}",
                requires_organization=True
            ),
        }

    def _validate_resource_type(self, resource_type: str) -> ResourceType:
        """Validate and convert string resource type to enum."""
        try:
            return ResourceType(resource_type.lower())
        except ValueError:
            raise InvalidResourceTypeError(f"Invalid resource type: {resource_type}")

    def _validate_organization_requirement(self, resource_type: ResourceType) -> None:
        """Validate that organization is provided when required."""
        if self._endpoints[resource_type].requires_organization and not self.organization:
            raise ValueError(f"Organization is required for resource type: {resource_type.value}")

    def _build_url(self, resource_type: ResourceType, identifier: str, **kwargs) -> str:
        """Build the complete URL for the resource request."""
        endpoint = self._endpoints[resource_type]
        path = endpoint.path_template.format(
            organization=self.organization,
            identifier=identifier,
            **kwargs
        )
        return f"{self.base_url}/{path}"

    async def _handle_response(self, response: Any, resource_type: ResourceType) -> Dict[str, Any]:
        """Handle and validate the API response."""
        if not response:
            raise ResourceNotFoundError(f"Resource not found: {resource_type.value}")
        
        # Add additional validation or transformation logic here if needed
        return response

    async def get_resource(
        self,
        resource_type: str,
        identifier: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch a single resource from GitHub API with improved error handling and validation.
        
        Args:
            resource_type: Type of resource to fetch
            identifier: Primary identifier for the resource
            **kwargs: Additional parameters needed for specific resource types
            
        Returns:
            Dict containing the resource data
            
        Raises:
            InvalidResourceTypeError: If the resource type is not supported
            ResourceNotFoundError: If the resource is not found
            ValueError: If required parameters are missing
        """
        try:
            # Validate resource type
            resource_type_enum = self._validate_resource_type(resource_type)
            
            # Validate organization requirement
            self._validate_organization_requirement(resource_type_enum)
            
            # Build URL
            url = self._build_url(resource_type_enum, identifier, **kwargs)
            
            # Fetch resource
            response = await self.client.fetch_with_retry(url)
            
            # Handle and validate response
            return await self._handle_response(response, resource_type_enum)
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(f"Resource not found: {resource_type} with identifier {identifier}")
            raise
        except Exception as e:
            logger.error(f"Error fetching {resource_type} with identifier {identifier}: {e}")
            raise

    async def get_resource_with_retry(
        self,
        resource_type: str,
        identifier: str,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch a resource with retry logic for handling transient failures.
        
        Args:
            resource_type: Type of resource to fetch
            identifier: Primary identifier for the resource
            max_retries: Maximum number of retry attempts
            **kwargs: Additional parameters needed for specific resource types
            
        Returns:
            Dict containing the resource data
        """
        for attempt in range(max_retries):
            try:
                return await self.get_resource(resource_type, identifier, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed for {resource_type} {identifier}: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff 