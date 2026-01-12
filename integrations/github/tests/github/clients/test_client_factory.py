import pytest

from github.clients.client_factory import GitHubAuthenticatorFactory
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.auth.github_app_authenticator import GitHubAppAuthenticator
from github.helpers.exceptions import MissingCredentials


class TestGitHubAuthenticatorFactory:
    def test_create_with_token_when_oauth_disabled(self) -> None:
        """Test that PAT authenticator is created when OAuth is disabled and token is provided."""
        authenticator = GitHubAuthenticatorFactory.create(
            github_host="https://api.github.com",
            token="test-token",
        )

        assert isinstance(authenticator, PersonalTokenAuthenticator)
        assert authenticator._token.token == "test-token"

    def test_create_with_token_and_app_credentials(self) -> None:
        """Test that GitHub App auth is preferred when both token and app credentials are provided."""
        authenticator = GitHubAuthenticatorFactory.create(
            github_host="https://api.github.com",
            token="test-token",
            organization="test-org",
            app_id="test-app-id",
            installation_id="12345",
            private_key="-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
        )

        # Should use GitHub App authenticator, not PAT
        assert isinstance(authenticator, GitHubAppAuthenticator)
        assert authenticator.organization == "test-org"
        assert authenticator.app_id == "test-app-id"

    def test_create_with_app_credentials_when_oauth_disabled(self) -> None:
        """Test that GitHub App authenticator is created when OAuth is disabled and app credentials are provided."""
        # OAuth is disabled by default in conftest.py, so no patch needed
        authenticator = GitHubAuthenticatorFactory.create(
            github_host="https://api.github.com",
            organization="test-org",
            app_id="test-app-id",
            installation_id="12345",
            private_key="-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
        )

        assert isinstance(authenticator, GitHubAppAuthenticator)
        assert authenticator.organization == "test-org"
        assert authenticator.app_id == "test-app-id"

    def test_create_prefers_app_over_token_when_oauth_disabled(self) -> None:
        """Test that GitHub App credentials take precedence over token when OAuth is disabled."""
        # OAuth is disabled by default in conftest.py, so no patch needed
        authenticator = GitHubAuthenticatorFactory.create(
            github_host="https://api.github.com",
            token="test-token",
            organization="test-org",
            app_id="test-app-id",
            installation_id="12345",
            private_key="-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
        )

        # GitHub App should take precedence
        assert isinstance(authenticator, GitHubAppAuthenticator)
        assert authenticator.organization == "test-org"
        assert authenticator.app_id == "test-app-id"

    def test_create_raises_error_when_no_credentials(self) -> None:
        """Test that MissingCredentials is raised when no credentials are provided."""
        with pytest.raises(
            MissingCredentials, match="No valid GitHub credentials provided"
        ):
            GitHubAuthenticatorFactory.create(
                github_host="https://api.github.com",
            )
