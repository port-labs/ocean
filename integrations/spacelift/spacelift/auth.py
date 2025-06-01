import asyncio
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean


@dataclass
class AuthConfig:
    """Configuration for Spacelift authentication."""

    api_key_id: Optional[str] = None
    api_key_secret: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_token: Optional[str] = None


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class SpacelifAuthenticator:
    """Handles Spacelift authentication and token management."""

    def __init__(self):
        self.http_client = http_async_client
        self.auth_config = self._load_auth_config()
        self._current_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _load_auth_config(self) -> AuthConfig:
        """Load authentication configuration from Ocean context."""
        config = ocean.integration_config
        return AuthConfig(
            api_key_id=config.get("spacelift_api_key_id"),
            api_key_secret=config.get("spacelift_api_key_secret"),
            api_endpoint=config.get("spacelift_api_endpoint"),
            api_token=config.get("spacelift_api_token"),
        )

    async def ensure_authenticated(self) -> str:
        """Ensure we have a valid authentication token and return it."""
        if self._is_token_valid():
            return self._current_token
            
        if self.auth_config.api_token:
            # Use provided API token directly
            self._current_token = self.auth_config.api_token
            # API tokens expire after 10 hours according to Spacelift docs
            self._token_expires_at = datetime.now() + timedelta(hours=9, minutes=30)
            logger.info("Using provided API token")
        elif self.auth_config.api_key_id and self.auth_config.api_key_secret:
            # Exchange API key for token
            await self._authenticate_with_api_key()
        else:
            raise AuthenticationError(
                "No valid authentication credentials provided. "
                "Please provide either spaceliftApiToken or both spaceliftApiKeyId and spaceliftApiKeySecret"
            )
        
        return self._current_token

    def _is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        if not self._current_token:
            return False
        if not self._token_expires_at:
            return False
        # Add 5 minute buffer to avoid token expiry during requests
        return datetime.now() + timedelta(minutes=5) < self._token_expires_at

    async def _authenticate_with_api_key(self) -> None:
        """Authenticate using API key and secret to get JWT token."""
        if not self.auth_config.api_endpoint:
            raise AuthenticationError(
                "spaceliftApiEndpoint is required when using API key authentication"
            )

        # Validate endpoint format
        if not self.auth_config.api_endpoint.endswith('/graphql'):
            if not self.auth_config.api_endpoint.endswith('/'):
                self.auth_config.api_endpoint += '/'
            self.auth_config.api_endpoint += 'graphql'

        logger.info("Authenticating with Spacelift API key")

        mutation = """
        mutation GetSpaceliftToken($id: ID!, $secret: String!) {
            apiKeyUser(id: $id, secret: $secret) {
                id
                jwt
            }
        }
        """

        variables = {
            "id": self.auth_config.api_key_id,
            "secret": self.auth_config.api_key_secret,
        }

        try:
            response = await self.http_client.request(
                method="POST",
                url=self.auth_config.api_endpoint,
                json={"query": mutation, "variables": variables},
                headers={"Content-Type": "application/json"},
            )

            if response.is_error:
                raise AuthenticationError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )

            data = response.json()

            if "errors" in data:
                error_messages = [error.get("message", "Unknown error") for error in data["errors"]]
                raise AuthenticationError(
                    f"GraphQL authentication error: {', '.join(error_messages)}"
                )

            api_key_user = data["data"]["apiKeyUser"]
            if not api_key_user:
                raise AuthenticationError("Failed to obtain JWT token from API key")

            jwt_token = api_key_user["jwt"]
            self._current_token = jwt_token
            # JWT tokens expire after 10 hours according to Spacelift docs
            self._token_expires_at = datetime.now() + timedelta(hours=9, minutes=30)

            logger.success("Successfully authenticated with Spacelift")

        except Exception as e:
            logger.error(f"Failed to authenticate with Spacelift: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")

    def get_api_endpoint(self) -> Optional[str]:
        """Get the API endpoint URL."""
        return self.auth_config.api_endpoint

    def invalidate_token(self) -> None:
        """Invalidate the current token to force re-authentication."""
        self._current_token = None
        self._token_expires_at = None 