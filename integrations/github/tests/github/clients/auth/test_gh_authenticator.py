from datetime import datetime, timedelta, timezone
import pytest
import httpx
from unittest.mock import AsyncMock, Mock, patch, PropertyMock

from github.clients.auth.abstract_authenticator import GitHubToken
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator


class TestGithubAuthenticator:
    @pytest.fixture
    def github_auth(self) -> GitHubAppInstallationAuthenticator:
        return GitHubAppInstallationAuthenticator(
            app_auth=GitHubAppAuthenticator(
                app_id="test-app-id",
                private_key="test-private-key",
                github_host="https://api.github.com",
            ),
            organization="test-org",
            installation_id="12345",
        )

    def test_rate_limit_scope_uses_organization(
        self, github_auth: GitHubAppInstallationAuthenticator
    ) -> None:
        assert github_auth.rate_limit_scope == "installation:test-org"

    @pytest.mark.asyncio
    async def test_token_generated(
        self, github_auth: GitHubAppInstallationAuthenticator
    ) -> None:
        mock_install_token = GitHubToken(
            token="mock-installation-token",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

        with patch.object(
            github_auth.app_auth,
            "fetch_installation_access_token",
            AsyncMock(return_value=mock_install_token),
        ) as mock_fetch_install_token:
            await github_auth.get_token()

            mock_fetch_install_token.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_token_refreshed_on_expiry(
        self, github_auth: GitHubAppInstallationAuthenticator
    ) -> None:
        mock_new_token = GitHubToken(
            token="mock-new-installation-token",
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=11)).isoformat(),
        )

        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        github_auth.cached_installation_token = GitHubToken(
            token="mock-expired-token", expires_at=expired_time
        )

        with patch.object(
            github_auth.app_auth,
            "fetch_installation_access_token",
            AsyncMock(return_value=mock_new_token),
        ) as mock_fetch_install_token:
            await github_auth.get_headers()

            mock_fetch_install_token.assert_called_once_with("12345")
            assert github_auth.cached_installation_token == mock_new_token

    @pytest.mark.asyncio
    async def test_installation_id_provided_no_fetch_call(
        self, github_auth: GitHubAppInstallationAuthenticator
    ) -> None:
        mock_install_token = GitHubToken(
            token="mock-installation-token",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

        with (
            patch.object(
                github_auth.app_auth,
                "fetch_installation_access_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_fetch_install_token,
            patch.object(
                github_auth.app_auth,
                "get_installation_id_for_organization",
                AsyncMock(),
            ) as mock_get_installation_id,
        ):
            token = await github_auth.get_token()

            mock_fetch_install_token.assert_called_once_with("12345")
            mock_get_installation_id.assert_not_called()
            assert token == mock_install_token

    @pytest.mark.asyncio
    async def test_installation_id_fetched_when_not_provided(self) -> None:
        github_auth = GitHubAppInstallationAuthenticator(
            app_auth=GitHubAppAuthenticator(
                app_id="test-app-id",
                private_key="test-private-key",
                github_host="https://api.github.com",
            ),
            organization="my-org",
        )
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"id": 99999}
        mock_response.raise_for_status = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch.object(
                github_auth.app_auth,
                "get_headers",
                AsyncMock(
                    return_value=AsyncMock(
                        as_dict=lambda: {"Authorization": "Bearer jwt"}
                    )
                ),
            ),
            patch.object(
                type(github_auth.app_auth),
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
        ):
            installation_id = await github_auth._get_installation_id()

            mock_client.get.assert_called_once_with(
                "https://api.github.com/users/my-org/installation",
                headers={"Authorization": "Bearer jwt"},
            )
            assert installation_id == "99999"
            assert github_auth.installation_id == "99999"

    @pytest.mark.asyncio
    async def test_client_returns_same_instance(
        self, github_auth: GitHubAppInstallationAuthenticator
    ) -> None:
        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60

            client_first = github_auth.client
            client_second = github_auth.client
            client_third = github_auth.client

            assert client_first is client_second
            assert client_second is client_third
            assert client_first is client_third

    @pytest.mark.asyncio
    async def test_different_authenticators_have_different_clients(self) -> None:
        auth1 = GitHubAppInstallationAuthenticator(
            app_auth=GitHubAppAuthenticator(
                app_id="app1", private_key="key1", github_host="https://api.github.com"
            ),
            organization="org1",
            installation_id="111",
        )
        auth2 = GitHubAppInstallationAuthenticator(
            app_auth=GitHubAppAuthenticator(
                app_id="app2", private_key="key2", github_host="https://api.github.com"
            ),
            organization="org2",
            installation_id="222",
        )

        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60

            client1 = auth1.client
            client2 = auth2.client

            assert client1 is not client2
            assert auth1.client is client1
            assert auth2.client is client2

    @pytest.mark.asyncio
    async def test_client_retries_on_500(
        self, github_auth: GitHubAppInstallationAuthenticator
    ) -> None:
        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            calls: list[int] = []

            async def fake_handle_async_request(
                self: httpx.AsyncHTTPTransport, request: httpx.Request
            ) -> httpx.Response:
                calls.append(1)
                headers = {"Content-Length": "0"}
                if len(calls) == 1:
                    return httpx.Response(500, headers=headers, request=request)
                return httpx.Response(200, headers=headers, request=request)

            with (
                patch.object(
                    httpx.AsyncHTTPTransport,
                    "handle_async_request",
                    fake_handle_async_request,
                ),
                patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
                patch.object(
                    github_auth,
                    "get_headers",
                    AsyncMock(
                        return_value=AsyncMock(
                            as_dict=lambda: {"Authorization": "Bearer test"}
                        )
                    ),
                ),
            ):
                client = github_auth.client
                resp = await client.get("https://api.github.com/test")
                await client.aclose()

            assert resp.status_code == 200
            assert len(calls) == 2
