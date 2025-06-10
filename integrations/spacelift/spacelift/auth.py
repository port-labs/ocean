from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import jwt

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


class SpaceliftAuthenticator:
    """Handles Spacelift authentication and token management."""

    def __init__(self) -> None:
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

    def _extract_token_expiry(self, token: str) -> Optional[datetime]:
        """Extract expiry time from JWT token if possible."""
        try:
            # Decode JWT token without verification to get expiry
            decoded = jwt.decode(token, options={"verify_signature": False})
            if "exp" in decoded:
                return datetime.fromtimestamp(decoded["exp"])
        except Exception as e:
            logger.debug(f"Could not decode JWT token to extract expiry: {e}")
        return None

    async def ensure_authenticated(self) -> str:
        """Ensure we have a valid authentication token and return it."""
        if self._is_token_valid() and self._current_token is not None:
            return self._current_token

        if self.auth_config.api_token:
            self._current_token = self.auth_config.api_token
            # Try to extract expiry from the token, fallback to hardcoded value
            extracted_expiry = self._extract_token_expiry(self.auth_config.api_token)
            if extracted_expiry:
                self._token_expires_at = extracted_expiry
                logger.info("Using provided API token with extracted expiry time")
            else:
                # Fallback to hardcoded expiry with warning
                self._token_expires_at = datetime.now() + timedelta(hours=9, minutes=30)
                logger.warning("Using provided API token with hardcoded expiry time (9h 30m). Consider validating token lifetime.")
            logger.info("Using provided API token")
        elif self.auth_config.api_key_id and self.auth_config.api_key_secret:
            await self._authenticate_with_api_key()
        else:
            raise AuthenticationError(
                "No valid authentication credentials provided. "
                "Please provide either spaceliftApiToken or both spaceliftApiKeyId and spaceliftApiKeySecret"
            )

        if self._current_token is None:
            raise AuthenticationError("Failed to obtain authentication token")
        return self._current_token

    def _is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        if not self._current_token:
            return False
        if not self._token_expires_at:
            return False
        return datetime.now() + timedelta(minutes=5) < self._token_expires_at

    async def _authenticate_with_api_key(self) -> None:
        """Authenticate using API key and secret to get JWT token."""
        if not self.auth_config.api_endpoint:
            raise AuthenticationError(
                "spaceliftApiEndpoint is required when using API key authentication"
            )

        # Use local variable instead of mutating configuration
        graphql_endpoint = self.auth_config.api_endpoint
        if not graphql_endpoint.endswith("/graphql"):
            if not graphql_endpoint.endswith("/"):
                graphql_endpoint += "/"
            graphql_endpoint += "graphql"

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
                url=graphql_endpoint,
                json={"query": mutation, "variables": variables},
                headers={"Content-Type": "application/json"},
            )

            if response.is_error:
                raise AuthenticationError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )

            data = response.json()

            if "errors" in data:
                error_messages = [
                    error.get("message", "Unknown error") for error in data["errors"]
                ]
                raise AuthenticationError(
                    f"GraphQL authentication error: {', '.join(error_messages)}"
                )

            api_key_user = data["data"]["apiKeyUser"]
            if not api_key_user:
                raise AuthenticationError("Failed to obtain JWT token from API key")

            jwt_token = api_key_user["jwt"]
            self._current_token = jwt_token
            
            # Extract expiry from JWT token, fallback to hardcoded value
            extracted_expiry = self._extract_token_expiry(jwt_token)
            if extracted_expiry:
                self._token_expires_at = extracted_expiry
                logger.info("Successfully authenticated with Spacelift using extracted token expiry")
            else:
                # Fallback to hardcoded expiry with warning
                self._token_expires_at = datetime.now() + timedelta(hours=9, minutes=30)
                logger.warning("Using hardcoded token expiry time (9h 30m). Could not extract expiry from JWT.")

            logger.success("Successfully authenticated with Spacelift")

        except Exception as e:
            logger.error(f"Failed to authenticate with Spacelift: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")

    def get_api_endpoint(self) -> str:
        """Get the API endpoint URL with GraphQL suffix."""
        if self.auth_config.api_endpoint is None:
            raise AuthenticationError("API endpoint is not configured")
        
        # Use local variable instead of mutating configuration
        graphql_endpoint = self.auth_config.api_endpoint
        if not graphql_endpoint.endswith("/graphql"):
            if not graphql_endpoint.endswith("/"):
                graphql_endpoint += "/"
            graphql_endpoint += "graphql"
        
        return graphql_endpoint

    def invalidate_token(self) -> None:
        """Invalidate the current token to force re-authentication."""
        self._current_token = None
        self._token_expires_at = None
