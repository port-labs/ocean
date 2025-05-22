import pytest
from unittest.mock import AsyncMock, patch

from github.helpers.app import GithubApp


@pytest.mark.asyncio
class TestGithubAppRestClient:
    @pytest.fixture
    def app_client(self) -> GithubApp:
        """Fixture to create a GithubAppRestClient instance."""
        return GithubApp(
            organization="test-org",
            github_host="https://api.github.com",
            app_id="test-app-id",
            private_key="test-private-key",
        )

    async def test_token_generated(self, app_client: GithubApp) -> None:
        """Test that set_up correctly generates and sets the installation token."""
        mock_install_id = 12345
        mock_install_token = "mock-installation-token"

        with (
            patch.object(
                app_client,
                "_get_installation_id",
                AsyncMock(return_value=mock_install_id),
            ) as mock_get_install_id,
            patch.object(
                app_client,
                "_get_installation_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_get_install_token,
        ):
            await app_client.get_token()

            # Verify that the necessary internal methods were called
            mock_get_install_id.assert_called_once()
            mock_get_install_token.assert_called_once()
