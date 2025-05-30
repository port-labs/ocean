from datetime import datetime, timedelta, timezone
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

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
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
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
                        expires_at=datetime.now(timezone.utc) + timedelta(minutes=11),
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

    async def test_fetch_installation_token_parses_timezone_correctly(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Test that installation token parsing correctly handles 'Z' and timezone awareness."""
        mock_installation_id = 12345
        mock_token_data = {
            "token": "ghs_mocktoken",
            "expires_at": "2024-01-01T12:34:56Z",  # GitHub's typical timestamp format
        }
        github_auth.installation_id = mock_installation_id
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_token_data
        mock_response.raise_for_status.return_value = None

        with (
            patch.object(github_auth, "_generate_jwt", MagicMock(return_value="token")),
            patch(
                "port_ocean.utils.http_async_client.post",
                AsyncMock(return_value=mock_response),
            ),
        ):
            token = await github_auth._fetch_installation_token()

            assert token.token == "ghs_mocktoken"
            assert isinstance(token.expires_at, datetime)
            assert token.expires_at.tzinfo is not None
            assert token.expires_at == datetime(
                2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc
            )
