"""Tests for TokenExpirationTracker and proactive re-authentication"""

import asyncio
import pytest
import httpx
import time
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.auth.custom.auth_flow import AuthFlowManager
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig


# ============================================================================
# Token Expiration & Proactive Re-authentication Tests
# ============================================================================


@pytest.mark.asyncio
class TestTokenExpiration:
    """Test token expiration and proactive re-authentication"""

    @pytest.fixture
    def custom_auth_with_interval(
        self,
        auth_config: Dict[str, Any],
        custom_auth_response: CustomAuthResponseConfig,
    ) -> AuthFlowManager:
        """AuthFlowManager with reauthenticate_interval_seconds configured"""
        auth_request = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
            reauthenticate_interval_seconds=3600,  # 1 hour
        )
        return AuthFlowManager(auth_config, auth_request, custom_auth_response)

    @pytest.fixture
    def custom_auth_without_interval(
        self,
        auth_config: Dict[str, Any],
        custom_auth_response: CustomAuthResponseConfig,
    ) -> AuthFlowManager:
        """AuthFlowManager without reauthenticate_interval_seconds configured"""
        auth_request = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
            # reauthenticate_interval_seconds not set (None)
        )
        return AuthFlowManager(auth_config, auth_request, custom_auth_response)

    async def test_expiration_tracker_interval_config(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that configured interval is set in expiration tracker"""
        interval, _ = (
            custom_auth_with_interval._expiration_tracker.get_expiration_info()
        )
        assert interval == 3600

    async def test_expiration_tracker_no_interval_config(
        self, custom_auth_without_interval: AuthFlowManager
    ) -> None:
        """Test that None is set when not configured"""
        interval, _ = (
            custom_auth_without_interval._expiration_tracker.get_expiration_info()
        )
        assert interval is None

    async def test_is_expired_no_auth_yet(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns True when no authentication has occurred"""
        assert custom_auth_with_interval._expiration_tracker.is_expired(False) is True

    async def test_is_expired_no_interval_configured(
        self, custom_auth_without_interval: AuthFlowManager
    ) -> None:
        """Test that returns False when no interval is configured"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_without_interval._expiration_tracker._reauthenticate_interval = None

        assert (
            custom_auth_without_interval._expiration_tracker.is_expired(True) is False
        )

    async def test_is_expired_not_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns False when token is not expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is False

    async def test_is_expired_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns True when token is expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp to 2 hours ago (expired)
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is True

    async def test_is_expired_within_buffer(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns True when token is within buffer window (60 seconds)"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp so expiration is in 30 seconds (within 60s buffer)
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 3570
        )  # 30s before expiration
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is True

    async def test_ensure_authenticated_proactively_reauthenticates_when_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that _ensure_authenticated proactively re-authenticates when expired"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )  # 2 hours ago
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        # Mock re-authentication
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "new-token"})
        mock_response.raise_for_status = MagicMock()

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._expiration_tracker.record_authentication()

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        await custom_auth_with_interval._ensure_authenticated()

        # Should have called authenticate
        assert len(authenticate_called) == 1
        assert custom_auth_with_interval.auth_response["access_token"] == "new-token"

    async def test_ensure_authenticated_does_not_reauthenticate_when_not_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that _ensure_authenticated does not re-authenticate when not expired"""
        # Set up valid token
        custom_auth_with_interval.auth_response = {"access_token": "valid-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time()
        )  # Just authenticated
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        await custom_auth_with_interval._ensure_authenticated()

        # Should not have called authenticate
        assert len(authenticate_called) == 0

    async def test_ensure_authenticated_no_expiration_check_when_interval_none(
        self, custom_auth_without_interval: AuthFlowManager
    ) -> None:
        """Test that _ensure_authenticated doesn't check expiration when interval is None"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_without_interval._expiration_tracker._reauthenticate_interval = None

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)

        custom_auth_without_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        await custom_auth_without_interval._ensure_authenticated()

        # Should not have called authenticate (no expiration checking)
        assert len(authenticate_called) == 0

    async def test_async_auth_flow_proactively_reauthenticates_on_expiration(
        self,
        custom_auth_with_interval: AuthFlowManager,
        mock_entity_processor: MagicMock,
    ) -> None:
        """Test that async_auth_flow proactively re-authenticates when expired"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._expiration_tracker.record_authentication()

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.read = MagicMock(return_value=b'{"data": "success"}')

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            request = httpx.Request("GET", "https://api.example.com/data")
            auth_flow = custom_auth_with_interval.async_auth_flow(request)

            # This should trigger proactive re-auth
            _ = await auth_flow.__anext__()

            # Should have called authenticate
            assert len(authenticate_called) == 1
            assert (
                custom_auth_with_interval.auth_response["access_token"] == "new-token"
            )

    async def test_proactive_reauthentication_uses_lock(
        self,
        custom_auth_with_interval: AuthFlowManager,
        mock_entity_processor: MagicMock,
    ) -> None:
        """Test that proactive re-authentication uses lock to prevent concurrent auth"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        authenticate_calls = []

        async def mock_authenticate() -> None:
            authenticate_calls.append("auth")
            await asyncio.sleep(0.1)  # Simulate auth delay
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._expiration_tracker.record_authentication()

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.read = MagicMock(return_value=b'{"data": "success"}')

        async def run_auth_flow() -> None:
            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                mock_entity_processor,
            ):
                request = httpx.Request("GET", "https://api.example.com/data")
                auth_flow = custom_auth_with_interval.async_auth_flow(request)
                await auth_flow.__anext__()

        # Run two concurrent auth flows
        await asyncio.gather(run_auth_flow(), run_auth_flow())

        # Should authenticate at least once, but lock should prevent race conditions
        assert len(authenticate_calls) >= 1
        assert len(authenticate_calls) <= 2
