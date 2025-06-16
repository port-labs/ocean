"""Spacelift GraphQL client for Ocean integration."""

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Callable

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


class SpaceliftClient:
    """Client for Spacelift GraphQL API."""

    def __init__(
        self,
        api_endpoint: str,
        api_key_id: str,
        api_key_secret: str,
        max_retries: int = 2,
    ):
        """Initialize the Spacelift client.

        Args:
            api_endpoint: Spacelift GraphQL API endpoint
            api_key_id: Spacelift API key ID
            api_key_secret: Spacelift API key secret
        """
        self.api_endpoint = api_endpoint
        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret
        self._token: Optional[str] = None
        self._client = http_async_client

        # Rate limiting
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.1  # 100ms between requests (10 req/sec)

        # Token management
        self._token_expires_at: Optional[float] = None
        self._token_refresh_threshold: float = (
            300  # Refresh token 5 minutes before expiry
        )

        # Retry configuration from environment variable
        self._max_retries: int = max_retries

    async def __aenter__(self):
        """Async context manager entry."""
        await self._authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # No cleanup needed for this client
        pass

    async def _authenticate(self) -> None:
        """Authenticate with Spacelift and get JWT token."""
        mutation = """
        mutation GetSpaceliftToken($id: ID!, $secret: String!) {
            apiKeyUser(id: $id, secret: $secret) {
                jwt
            }
        }
        """

        variables = {"id": self.api_key_id, "secret": self.api_key_secret}

        response = await self._client.post(
            self.api_endpoint,
            json={"query": mutation, "variables": variables},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            raise Exception(f"Authentication failed: {data['errors']}")

        if not data["data"]["apiKeyUser"] or not data["data"]["apiKeyUser"]["jwt"]:
            raise Exception("Authentication failed: No token returned")

        self._token = data["data"]["apiKeyUser"]["jwt"]
        # Set token expiry time (JWT tokens typically last 1 hour, we'll assume 50 minutes to be safe)
        self._token_expires_at = time.time() + (50 * 60)  # 50 minutes from now
        logger.info("Successfully authenticated with Spacelift")

    async def _wait_for_rate_limit(self, retry_after: Optional[float] = None) -> None:
        """Wait if necessary due to rate limiting.

        Args:
            retry_after: Optional retry-after time in seconds from API response
        """
        if retry_after:
            # Use the retry-after time provided by the API
            sleep_time = retry_after
            logger.warning(
                f"Rate limited by API: waiting {sleep_time:.3f}s before retry"
            )
        else:
            # Use default backoff strategy
            sleep_time = self._min_request_interval
            logger.warning(
                f"Rate limiting detected: waiting {sleep_time:.3f}s before retry"
            )

        await asyncio.sleep(sleep_time)
        self._last_request_time = time.time()

    async def _is_rate_limit_error(self, response) -> Optional[float]:
        """Check if response indicates rate limiting and extract retry-after time.

        Args:
            response: HTTP response object

        Returns:
            Retry-after time in seconds if rate limited, None otherwise
        """
        # Check HTTP status codes for rate limiting
        if response.status_code == 429:  # Too Many Requests
            # Try to get retry-after header
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
            return self._min_request_interval

        # Check for other potential rate limiting status codes
        if response.status_code in [
            502,
            503,
            504,
        ]:  # Bad Gateway, Service Unavailable, Gateway Timeout
            return self._min_request_interval

        return None

    async def _is_graphql_rate_limit_error(self, data: Dict[str, Any]) -> bool:
        """Check if GraphQL response contains rate limiting errors.

        Args:
            data: GraphQL response data

        Returns:
            True if rate limited, False otherwise
        """
        errors = data.get("errors", [])

        rate_limit_indicators = [
            "rate limit",
            "rate-limit",
            "too many requests",
            "throttled",
            "quota exceeded",
            "limit exceeded",
        ]

        return any(
            any(indicator in str(error).lower() for indicator in rate_limit_indicators)
            for error in errors
        )

    async def _is_token_expired(self) -> bool:
        """Check if the current token is expired or about to expire."""
        if not self._token or not self._token_expires_at:
            return True

        current_time = time.time()
        return current_time >= (self._token_expires_at - self._token_refresh_threshold)

    async def _handle_auth_error(self, response_data: Dict[str, Any]) -> bool:
        """Handle authentication errors and attempt to re-authenticate.

        Args:
            response_data: The response data from a failed request

        Returns:
            True if re-authentication was successful, False otherwise
        """
        errors = response_data.get("errors", [])

        # Check for authentication-related errors
        auth_error_indicators = [
            "unauthorized",
            "unauthenticated",
            "token",
            "jwt",
            "expired",
            "invalid",
            "authentication",
            "permission",
        ]

        is_auth_error = any(
            any(indicator in str(error).lower() for indicator in auth_error_indicators)
            for error in errors
        )

        if is_auth_error:
            logger.warning(
                "Authentication error detected, attempting to re-authenticate"
            )
            try:
                await self._authenticate()
                return True
            except Exception as e:
                logger.error(f"Re-authentication failed: {e}")
                return False

        return False

    async def _graphql_request(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a GraphQL request to Spacelift with rate limiting and token management.

        Args:
            query: GraphQL query or mutation
            variables: Optional variables for the query

        Returns:
            The response data
        """
        # Check if token needs refresh before making request
        if await self._is_token_expired():
            logger.info("Token expired or about to expire, refreshing...")
            await self._authenticate()

        for attempt in range(self._max_retries + 1):
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }

            payload = {"query": query}
            if variables:
                payload["variables"] = variables

            try:
                response = await self._client.post(
                    self.api_endpoint, json=payload, headers=headers
                )

                # Check for rate limiting before raising for status
                retry_after = await self._is_rate_limit_error(response)
                if retry_after is not None:
                    if attempt < self._max_retries:
                        await self._wait_for_rate_limit(retry_after)
                        continue
                    else:
                        logger.error("Maximum retries exceeded for rate limiting")
                        response.raise_for_status()

                response.raise_for_status()

                data = response.json()

                # Check for GraphQL-level rate limiting
                if "errors" in data and await self._is_graphql_rate_limit_error(data):
                    if attempt < self._max_retries:
                        logger.warning("GraphQL rate limiting detected")
                        await self._wait_for_rate_limit()
                        continue
                    else:
                        raise Exception(
                            f"GraphQL request failed due to rate limiting: {data['errors']}"
                        )

                # Check for other GraphQL errors
                if "errors" in data:
                    # Try to handle authentication errors
                    if attempt < self._max_retries and await self._handle_auth_error(
                        data
                    ):
                        logger.info(
                            f"Retrying request after re-authentication (attempt {attempt + 1}/{self._max_retries})"
                        )
                        continue

                    raise Exception(f"GraphQL request failed: {data['errors']}")

                return data["data"]

            except Exception as e:
                if attempt < self._max_retries:
                    # Check if this might be a network or temporary error
                    if (
                        "401" in str(e)
                        or "403" in str(e)
                        or "unauthorized" in str(e).lower()
                    ):
                        logger.warning(
                            f"Authentication error on attempt {attempt + 1}, re-authenticating..."
                        )
                        await self._authenticate()
                        continue

                # Re-raise the exception if we've exhausted retries or it's not an auth error
                raise

    async def _paginated_query(
        self,
        query: str,
        response_field: str,
        variables: Optional[Dict[str, Any]] = None,
        data_extractor: Optional[
            Callable[[Dict[str, Any]], List[Dict[str, Any]]]
        ] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Execute a paginated GraphQL query.

        Args:
            query: GraphQL query with cursor pagination
            response_field: Field name in response data (e.g., 'spaces', 'stacks')
            variables: Additional variables for the query (excluding cursor)
            data_extractor: Optional function to extract data from response

        Yields:
            Batches of resource data
        """
        cursor = None
        base_variables = variables or {}

        while True:
            # Add cursor to variables
            query_variables = {**base_variables}
            if cursor:
                query_variables["cursor"] = cursor

            data = await self._graphql_request(query, query_variables)

            # Extract the response field data
            if data_extractor:
                items = data_extractor(data)
                if items:
                    yield items
                # For custom extractors, we need to determine if there are more pages
                # This assumes the extractor handles pagination info internally
                break
            else:
                # Standard pagination format
                field_data = data.get(response_field)
                if not field_data:
                    break

                edges = field_data.get("edges", [])
                if not edges:
                    break

                items = [edge["node"] for edge in edges]
                yield items

                page_info = field_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break
                cursor = page_info.get("endCursor")

    async def get_spaces(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all spaces from Spacelift.

        Yields:
            Batches of space data
        """
        query = """
        query GetSpaces($cursor: Cursor) {
            spaces(first: 100, after: $cursor) {
                edges {
                    node {
                        id
                        name
                        description
                        labels
                        createdAt
                        parentSpace
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """

        async for batch in self._paginated_query(query, "spaces"):
            yield batch

    async def get_stacks(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all stacks from Spacelift.

        Yields:
            Batches of stack data
        """
        query = """
        query GetStacks($cursor: Cursor) {
            stacks(first: 100, after: $cursor) {
                edges {
                    node {
                        id
                        name
                        space
                        administrative
                        state
                        description
                        repository
                        repositoryURL
                        provider
                        labels
                        branch
                        namespace
                        createdAt
                        trackedRuns {
                            id
                            state
                            createdAt
                            updatedAt
                            triggeredBy
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """

        async for batch in self._paginated_query(query, "stacks"):
            yield batch

    async def get_runs(
        self, stack_id: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get runs from Spacelift.

        Args:
            stack_id: Optional stack ID to filter runs

        Yields:
            Batches of run data
        """
        if stack_id:
            query = """
            query GetStackRuns($stackId: ID!, $cursor: Cursor) {
                stack(id: $stackId) {
                    runs(first: 100, after: $cursor) {
                        edges {
                            node {
                                id
                                type
                                state
                                createdAt
                                updatedAt
                                triggeredBy
                                branch
                                commit {
                                    hash
                                    message
                                    authorName
                                    timestamp
                                }
                                driftDetection
                                stack {
                                    id
                                    name
                                }
                            }
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                    }
                }
            }
            """

            def extract_stack_runs(data: Dict[str, Any]) -> List[Dict[str, Any]]:
                stack_data = data.get("stack", {})
                runs_data = stack_data.get("runs", {})
                edges = runs_data.get("edges", [])
                return [edge["node"] for edge in edges] if edges else []

            async for batch in self._paginated_query(
                query,
                "stack",
                variables={"stackId": stack_id},
                data_extractor=extract_stack_runs,
            ):
                yield batch
        else:
            query = """
            query GetRuns($cursor: Cursor) {
                runs(first: 100, after: $cursor) {
                    edges {
                        node {
                            id
                            type
                            state
                            createdAt
                            updatedAt
                            triggeredBy
                            branch
                            commit {
                                hash
                                message
                                authorName
                                timestamp
                            }
                            driftDetection
                            stack {
                                id
                                name
                            }
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
            """

            async for batch in self._paginated_query(query, "runs"):
                yield batch

    async def get_policies(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all policies from Spacelift.

        Yields:
            Batches of policy data
        """
        query = """
        query GetPolicies($cursor: Cursor) {
            policies(first: 100, after: $cursor) {
                edges {
                    node {
                        id
                        name
                        type
                        space
                        body
                        createdAt
                        updatedAt
                        labels
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """

        async for batch in self._paginated_query(query, "policies"):
            yield batch

    async def get_users(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all users from Spacelift.

        Yields:
            Batches of user data
        """
        query = """
        query {
            account {
                users {
                    id
                    username
                    name
                    email
                    isAdmin
                    isSuspended
                    createdAt
                    lastSeenAt
                }
            }
        }
        """

        def extract_users(data: Dict[str, Any]) -> List[Dict[str, Any]]:
            account_data = data.get("account", {})
            users = account_data.get("users", [])
            return users if users else []

        async for batch in self._paginated_query(
            query, "account", data_extractor=extract_users
        ):
            yield batch

    async def get_resource_batch(
        self, resource_type: str, **kwargs
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Generic method to get resources with pagination.

        Args:
            resource_type: Type of resource ('spaces', 'stacks', 'runs', 'policies', 'users')
            **kwargs: Additional arguments passed to the specific method

        Yields:
            Batches of resource data
        """
        method_map = {
            "spaces": self.get_spaces,
            "stacks": self.get_stacks,
            "runs": self.get_runs,
            "policies": self.get_policies,
            "users": self.get_users,
        }

        if resource_type not in method_map:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        method = method_map[resource_type]

        # Check if method accepts kwargs
        if resource_type == "runs" and kwargs:
            async for batch in method(**kwargs):
                yield batch
        else:
            async for batch in method():
                yield batch


def create_spacelift_client() -> SpaceliftClient:
    """Create a Spacelift client instance from configuration."""
    api_endpoint = ocean.integration_config.get("spacelift_api_endpoint")
    api_key_id = ocean.integration_config.get("spacelift_api_key_id")
    api_key_secret = ocean.integration_config.get("spacelift_api_key_secret")
    max_retries = int(ocean.integration_config.get("spacelift_max_retries", 2))

    if not all([api_endpoint, api_key_id, api_key_secret]):
        raise ValueError(
            "Missing required Spacelift configuration: "
            "spacelift_api_endpoint, spacelift_api_key_id, spacelift_api_key_secret"
        )

    return SpaceliftClient(api_endpoint, api_key_id, api_key_secret, max_retries)
