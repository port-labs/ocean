from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, patch

from github.clients.auth.abstract_authenticator import GitHubToken
from github.clients.auth.github_app_authenticator import GitHubAppAuthenticator


@pytest.mark.asyncio
class TestGithubAuthenticator:
    @pytest.fixture
    def github_auth(self) -> GitHubAppAuthenticator:
        """Fixture to create a GitHubAppAuthenticator instance."""
        return GitHubAppAuthenticator(
            organization="test-org",
            github_host="https://api.github.com",
            app_id="test-app-id",
            private_key="test-private-key",
        )

    async def test_token_generated(self, github_auth: GitHubAppAuthenticator) -> None:
        """Test that set_up correctly generates and sets the installation token."""
        mock_install_id = 12345
        mock_install_token = "mock-installation-token"

        with (
            patch.object(
                github_auth,
                "_fetch_installation_id",
                AsyncMock(return_value=mock_install_id),
            ) as mock_get_install_id,
            patch.object(
                github_auth,
                "_fetch_installation_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_get_install_token,
        ):
            await github_auth.get_token()

            # Verify that the necessary internal methods were called
            mock_get_install_token.assert_called_once()
            mock_get_install_id.assert_called_once()

    async def test_token_refreshed_on_expiry(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Test that a new token is fetched when the cached one expires."""
        mock_install_id = 12345
        mock_expired_token = "mock-expired-token"
        mock_new_token = "mock-new-installation-token"

        # Create an expired token
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        github_auth.cached_token = GitHubToken(
            token=mock_expired_token, expires_at=expired_time
        )

        with (
            patch.object(
                github_auth,
                "_fetch_installation_id",
                AsyncMock(return_value=mock_install_id),
            ) as mock_get_install_id,
            patch.object(
                github_auth,
                "_fetch_installation_token",
                AsyncMock(
                    return_value=GitHubToken(
                        token=mock_new_token,
                        expires_at=(
                            datetime.now(timezone.utc) + timedelta(minutes=11)
                        ).isoformat(),
                    )
                ),
            ) as mock_get_install_token,
        ):
            github_auth.installation_id = mock_install_id

            await github_auth.get_headers()

            mock_get_install_token.assert_called_once()
            mock_get_install_id.assert_not_called()
            assert github_auth.cached_token.token == mock_new_token

            mock_get_install_token.assert_called_once()
