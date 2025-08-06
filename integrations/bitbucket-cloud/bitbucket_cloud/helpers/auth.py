from abc import ABC, abstractmethod
from typing import Optional, List
from pydantic import BaseModel, Field
from loguru import logger
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException
from bitbucket_cloud.helpers.token_manager import TokenManager
from bitbucket_cloud.helpers.utils import (
    BitbucketRateLimiterConfig,
    BitbucketFileRateLimiterConfig,
)


class BitbucketHeaders(BaseModel):
    """Headers for Bitbucket API requests."""

    authorization: str = Field(alias="Authorization")
    accept: str = Field(alias="Accept", default="application/json")
    content_type: str = Field(alias="Content_Type", default="application/json")


class BitbucketToken(BaseModel):
    """Represents a Bitbucket token."""

    token: str


class AbstractAuth(ABC):
    """Abstract base class for authentication methods."""

    @abstractmethod
    def get_headers(self) -> BitbucketHeaders:
        """Get headers for API requests."""
        pass

    @abstractmethod
    def get_token(self) -> Optional[BitbucketToken]:
        """Get the current token if applicable."""
        pass


class BasicAuth(AbstractAuth):
    """Basic authentication using username and password."""

    def __init__(self, username: str, password: str):
        import base64

        self.encoded_credentials = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()

    def get_headers(self) -> BitbucketHeaders:
        return BitbucketHeaders(
            Authorization=f"Basic {self.encoded_credentials}",
            Accept="application/json",
            Content_Type="application/json",
        )

    def get_token(self) -> Optional[BitbucketToken]:
        return None


class SingleTokenAuth(AbstractAuth):
    """Single token authentication."""

    def __init__(self, token: str):
        self.token = token

    def get_headers(self) -> BitbucketHeaders:
        return BitbucketHeaders(
            Authorization=f"Bearer {self.token}",
            Accept="application/json",
            Content_Type="application/json",
        )

    def get_token(self) -> Optional[BitbucketToken]:
        return BitbucketToken(token=self.token)


class MultiTokenAuth(AbstractAuth):
    """Multi-token authentication with rotation support."""

    def __init__(self, tokens: List[str]):
        self._token_manager = TokenManager(
            tokens,
            BitbucketRateLimiterConfig.LIMIT,
            BitbucketRateLimiterConfig.WINDOW,
        )
        self._file_token_manager = TokenManager(
            tokens,
            BitbucketFileRateLimiterConfig.LIMIT,
            BitbucketFileRateLimiterConfig.WINDOW,
        )
        logger.info(
            f"Initialized MultiTokenAuth with {len(tokens)} tokens for rotation"
        )

    def get_headers(self) -> BitbucketHeaders:
        return BitbucketHeaders(
            Authorization=f"Bearer {self._token_manager.current_token}",
            Accept="application/json",
            Content_Type="application/json",
        )

    def get_token(self) -> Optional[BitbucketToken]:
        return BitbucketToken(token=self._token_manager.current_token)

    @property
    def token_manager(self) -> TokenManager:
        return self._token_manager

    @property
    def file_token_manager(self) -> TokenManager:
        return self._file_token_manager


class BitbucketAuthFacade:
    """Facade for creating and managing Bitbucket authentication."""

    @staticmethod
    def create(
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        workspace_token: Optional[str] = None,
    ) -> AbstractAuth:
        """
        Create the appropriate authentication method based on provided credentials.

        Args:
            username: Bitbucket username for basic auth
            app_password: Bitbucket app password for basic auth
            workspace_token: Comma-separated workspace tokens

        Returns:
            Appropriate authentication instance

        Raises:
            MissingIntegrationCredentialException: If no valid credentials provided
        """
        if workspace_token:
            tokens = [
                token.strip() for token in workspace_token.split(",") if token.strip()
            ]

            if not tokens:
                raise MissingIntegrationCredentialException(
                    "No valid tokens found in workspace_token. Please provide valid comma-separated tokens."
                )
            elif len(tokens) > 1:
                return MultiTokenAuth(tokens)
            else:
                return SingleTokenAuth(tokens[0])
        elif app_password and username:
            return BasicAuth(username, app_password)
        else:
            raise MissingIntegrationCredentialException(
                "Either workspace token or both username and app password must be provided"
            )
