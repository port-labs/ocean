from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, Mock, patch, PropertyMock

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
            installation_id="12345",
            private_key="test-private-key",
        )

    async def test_token_generated(self, github_auth: GitHubAppAuthenticator) -> None:
        """Test that set_up correctly generates and sets the installation token."""
        mock_jwt_token = GitHubToken(token="mock-jwt-token", expires_at=None)
        mock_install_token = "mock-installation-token"

        with (
            patch.object(
                github_auth,
                "_generate_jwt",
                Mock(return_value=mock_jwt_token),
            ) as mock_generate_jwt,
            patch.object(
                github_auth,
                "_fetch_installation_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_get_install_token,
        ):
            await github_auth.get_token()

            # Verify that the necessary internal methods were called
            mock_generate_jwt.assert_called_once()
            mock_get_install_token.assert_called_once()

    async def test_token_refreshed_on_expiry(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Test that a new token is fetched when the cached one expires."""
        mock_jwt_token = GitHubToken(token="mock-jwt-token", expires_at=None)
        mock_install_id = "12345"
        mock_expired_token = "mock-expired-token"
        mock_new_token = "mock-new-installation-token"

        # Create an expired token
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        github_auth.cached_installation_token = GitHubToken(
            token=mock_expired_token, expires_at=expired_time
        )

        with (
            patch.object(
                github_auth,
                "_generate_jwt",
                Mock(return_value=mock_jwt_token),
            ) as mock_generate_jwt,
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

            mock_generate_jwt.assert_called_once()
            mock_get_install_token.assert_called_once()
            assert github_auth.cached_installation_token.token == mock_new_token

            mock_get_install_token.assert_called_once()

    async def test_installation_id_provided_no_fetch_call(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        mock_jwt_token = GitHubToken(token="mock-jwt-token", expires_at=None)
        mock_install_token = GitHubToken(
            token="mock-installation-token",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

        mock_client = AsyncMock()

        with (
            patch.object(
                github_auth,
                "_generate_jwt",
                Mock(return_value=mock_jwt_token),
            ) as mock_generate_jwt,
            patch.object(
                github_auth,
                "_fetch_installation_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_get_install_token,
            patch.object(
                type(github_auth),
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
        ):
            token = await github_auth.get_token()

            mock_generate_jwt.assert_called_once()
            mock_get_install_token.assert_called_once_with(mock_jwt_token.token)

            # Verify no API call was made to fetch installation ID
            # (client.get should not be called for installation ID lookup)
            mock_client.get.assert_not_called()
            assert token == mock_install_token

    async def test_installation_id_not_provided_fetch_called(self) -> None:
        github_auth_no_id = GitHubAppAuthenticator(
            organization="test-org",
            github_host="https://api.github.com",
            app_id="test-app-id",
            private_key="test-private-key",
        )

        mock_jwt_token = GitHubToken(token="mock-jwt-token", expires_at=None)
        mock_fetched_installation_id = "67890"
        mock_install_token = GitHubToken(
            token="mock-installation-token",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

        with (
            patch.object(
                github_auth_no_id,
                "_generate_jwt",
                Mock(return_value=mock_jwt_token),
            ) as mock_generate_jwt,
            patch.object(
                github_auth_no_id,
                "_fetch_installation_id",
                AsyncMock(return_value=mock_fetched_installation_id),
            ) as mock_fetch_install_id,
            patch.object(
                github_auth_no_id,
                "_fetch_installation_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_get_install_token,
        ):
            token = await github_auth_no_id.get_token()

            mock_generate_jwt.assert_called_once()
            mock_fetch_install_id.assert_called_once_with(mock_jwt_token.token)
            mock_get_install_token.assert_called_once_with(mock_jwt_token.token)

            assert github_auth_no_id.installation_id == mock_fetched_installation_id
            assert token == mock_install_token

    async def test_fetch_installation_id_for_organization(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        mock_jwt_token = "mock-jwt-token"
        mock_installation_id = "12345"

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json = Mock(return_value={"id": mock_installation_id})
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        with (
            patch.object(
                github_auth,
                "_is_personal_org",
                AsyncMock(return_value=False),
            ) as mock_is_personal,
            patch.object(
                type(github_auth),
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
        ):
            installation_id = await github_auth._fetch_installation_id(mock_jwt_token)

            mock_is_personal.assert_called_once()

            expected_url = f"{github_auth.github_host}/orgs/{github_auth.organization}/installation"
            mock_client.get.assert_called_once_with(
                expected_url, headers={"Authorization": f"Bearer {mock_jwt_token}"}
            )

            assert installation_id == mock_installation_id

    async def test_fetch_installation_id_for_personal_org(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        mock_jwt_token = "mock-jwt-token"
        mock_installation_id = "67890"

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json = Mock(return_value={"id": mock_installation_id})
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        with (
            patch.object(
                github_auth,
                "_is_personal_org",
                AsyncMock(return_value=True),
            ) as mock_is_personal,
            patch.object(
                type(github_auth),
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
        ):
            installation_id = await github_auth._fetch_installation_id(mock_jwt_token)

            mock_is_personal.assert_called_once()

            expected_url = f"{github_auth.github_host}/users/{github_auth.organization}/installation"
            mock_client.get.assert_called_once_with(
                expected_url, headers={"Authorization": f"Bearer {mock_jwt_token}"}
            )

            assert installation_id == mock_installation_id
