from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
import httpx
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
                "is_personal_org",
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

            jwt_headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            mock_is_personal.assert_called_once_with(
                github_auth.github_host,
                github_auth.organization,
                headers=jwt_headers,
            )

            expected_url = f"{github_auth.github_host}/orgs/{github_auth.organization}/installation"
            mock_client.get.assert_called_once_with(
                expected_url,
                headers=jwt_headers,
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
                "is_personal_org",
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

            jwt_headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            mock_is_personal.assert_called_once_with(
                github_auth.github_host,
                github_auth.organization,
                headers=jwt_headers,
            )

            expected_url = f"{github_auth.github_host}/users/{github_auth.organization}/installation"
            mock_client.get.assert_called_once_with(
                expected_url,
                headers=jwt_headers,
            )

            assert installation_id == mock_installation_id

    async def test_is_personal_org_sends_auth_headers(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Verify is_personal_org forwards auth headers to the HTTP request."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json = Mock(return_value={"type": "Organization"})
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        headers = {"Authorization": "Bearer test-jwt"}

        with patch.object(
            type(github_auth),
            "client",
            new_callable=PropertyMock,
            return_value=mock_client,
        ):
            result = await github_auth.is_personal_org(
                "https://api.ghe.example.com",
                "MyOrg",
                headers=headers,
            )

        assert result is False
        mock_client.get.assert_called_once_with(
            "https://api.ghe.example.com/users/MyOrg",
            headers=headers,
        )

    async def test_is_personal_org_returns_true_for_user(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Verify is_personal_org returns True when GitHub reports type User."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json = Mock(return_value={"type": "User"})
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        with patch.object(
            type(github_auth),
            "client",
            new_callable=PropertyMock,
            return_value=mock_client,
        ):
            result = await github_auth.is_personal_org(
                "https://api.github.com",
                "my-user",
                headers={"Authorization": "Bearer tok"},
            )

        assert result is True

    async def test_is_personal_org_returns_false_on_error(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Verify is_personal_org returns False when the request fails."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "forbidden", request=Mock(), response=Mock(status_code=403)
        )

        with patch.object(
            type(github_auth),
            "client",
            new_callable=PropertyMock,
            return_value=mock_client,
        ):
            result = await github_auth.is_personal_org(
                "https://ghe.example.com",
                "Org",
                headers={"Authorization": "Bearer tok"},
            )

        assert result is False

    async def test_fetch_installation_id_passes_jwt_to_is_personal_org(
        self,
    ) -> None:
        """End-to-end: _fetch_installation_id passes JWT headers through
        to is_personal_org so the /users/{org} check is authenticated."""
        auth = GitHubAppAuthenticator(
            organization="DevopsZone",
            github_host="https://api.atpco.ghe.com",
            app_id="app-id",
            private_key="test-key",
        )

        jwt_token = "test-jwt-token"

        mock_client = AsyncMock()
        user_response = Mock()
        user_response.json = Mock(return_value={"type": "Organization"})
        user_response.raise_for_status = Mock()

        install_response = Mock()
        install_response.json = Mock(return_value={"id": "99999"})
        install_response.raise_for_status = Mock()

        def route_get(url: str, **kwargs: Any) -> Mock:
            if "/users/" in url:
                return user_response
            return install_response

        mock_client.get = AsyncMock(side_effect=route_get)

        with patch.object(
            type(auth),
            "client",
            new_callable=PropertyMock,
            return_value=mock_client,
        ):
            installation_id = await auth._fetch_installation_id(jwt_token)

        assert installation_id == "99999"

        jwt_headers = {"Authorization": f"Bearer {jwt_token}"}
        calls = mock_client.get.call_args_list
        assert len(calls) == 2

        personal_org_call = calls[0]
        assert personal_org_call.args[0] == "https://api.atpco.ghe.com/users/DevopsZone"
        assert personal_org_call.kwargs["headers"] == jwt_headers

        install_call = calls[1]
        assert (
            install_call.args[0]
            == "https://api.atpco.ghe.com/orgs/DevopsZone/installation"
        )
        assert install_call.kwargs["headers"] == jwt_headers

    async def test_client_returns_same_instance(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """Test that the client property returns the same cached instance on multiple accesses."""
        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60

            # Access client multiple times
            client_first = github_auth.client
            client_second = github_auth.client
            client_third = github_auth.client

            # All should be the exact same instance
            assert client_first is client_second
            assert client_second is client_third
            assert client_first is client_third

    async def test_different_authenticators_have_different_clients(self) -> None:
        """Test that different authenticator instances have their own cached clients."""
        auth1 = GitHubAppAuthenticator(
            organization="org1",
            github_host="https://api.github.com",
            app_id="app1",
            installation_id="111",
            private_key="key1",
        )
        auth2 = GitHubAppAuthenticator(
            organization="org2",
            github_host="https://api.github.com",
            app_id="app2",
            installation_id="222",
            private_key="key2",
        )

        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60

            client1 = auth1.client
            client2 = auth2.client

            # Different authenticators should have different client instances
            assert client1 is not client2

            # But each should still return the same instance on repeated access
            assert auth1.client is client1
            assert auth2.client is client2

    async def test_client_retries_on_500(
        self, github_auth: GitHubAppAuthenticator
    ) -> None:
        """
        Verify the authenticator's HTTP client retries on a 500 response.

        This test simulates a transient GitHub 500 followed by a 200 and asserts the
        request was attempted more than once.
        """
        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            calls: list[int] = []

            async def fake_handle_async_request(
                self: httpx.AsyncHTTPTransport, request: httpx.Request
            ) -> httpx.Response:
                calls.append(1)
                # Ensure we don't trigger response size logging reads.
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
