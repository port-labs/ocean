"""Tests for IP blocker: SSRF protection, DNS rebinding prevention, port.io bypass."""

import pytest
from unittest.mock import AsyncMock, patch

import httpx

from port_ocean.exceptions.clients import BlockedIPError
from port_ocean.helpers.ip_blocker import (
    IPBlockerTransport,
    _is_blocked,
)


class TestBlocked:
    def test_public_allowed(self) -> None:
        assert _is_blocked("8.8.8.8") is False
        assert _is_blocked("93.184.216.34") is False

    def test_private_loopback_blocked(self) -> None:
        assert _is_blocked("10.0.0.1") is True
        assert _is_blocked("127.0.0.1") is True
        assert _is_blocked("169.254.169.254") is True


class TestIPBlockerTransport:
    @pytest.mark.asyncio
    async def test_port_host_bypass(self) -> None:
        """Requests to *.port.io and *.getport.io skip the check."""
        wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)
        wrapped.handle_async_request.return_value = httpx.Response(
            200, request=httpx.Request("GET", "https://api.getport.io/")
        )
        transport = IPBlockerTransport(wrapped=wrapped)

        await transport.handle_async_request(
            httpx.Request("GET", "https://api.getport.io/")
        )
        await transport.handle_async_request(
            httpx.Request("GET", "https://app.port.io/")
        )

        assert wrapped.handle_async_request.await_count == 2
        # Request passed through as-is (no rewrite to IP)
        sent = wrapped.handle_async_request.call_args_list[0][0][0]
        assert sent.url.host == "api.getport.io"

    @pytest.mark.asyncio
    async def test_dns_rebinding_mitigation_pins_ip_keeps_host_sni(self) -> None:
        """URL is rewritten to validated IP (rebinding mitigation); Host + sni_hostname keep TLS working."""
        with patch(
            "port_ocean.helpers.ip_blocker._resolve_to_ip_addresses",
            return_value=["93.184.216.34"],
        ):
            wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)
            wrapped.handle_async_request.return_value = httpx.Response(
                200, request=httpx.Request("GET", "https://example.com/")
            )
            transport = IPBlockerTransport(wrapped=wrapped)

            await transport.handle_async_request(
                httpx.Request("GET", "https://example.com/foo?q=1")
            )

            sent: httpx.Request = wrapped.handle_async_request.call_args[0][0]
            assert sent.url.host == "93.184.216.34"
            assert sent.headers.get("host") == "example.com"
            assert sent.extensions.get("sni_hostname") == "example.com"
            assert str(sent.url) == "https://93.184.216.34/foo?q=1"

    @pytest.mark.asyncio
    async def test_https_sni_hostname_extension_set(self) -> None:
        """sni_hostname extension is set so TLS verifies cert against original hostname."""
        with patch(
            "port_ocean.helpers.ip_blocker._resolve_to_ip_addresses",
            return_value=["93.184.216.34"],
        ):
            wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)
            wrapped.handle_async_request.return_value = httpx.Response(
                200, request=httpx.Request("GET", "https://example.com/")
            )
            transport = IPBlockerTransport(wrapped=wrapped)
            await transport.handle_async_request(
                httpx.Request("GET", "https://example.com/")
            )
            sent: httpx.Request = wrapped.handle_async_request.call_args[0][0]
            assert sent.url.host == "93.184.216.34"
            assert sent.extensions.get("sni_hostname") == "example.com"

    @pytest.mark.asyncio
    async def test_ip_literal_passed_through(self) -> None:
        wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)
        wrapped.handle_async_request.return_value = httpx.Response(
            200, request=httpx.Request("GET", "https://93.184.216.34/")
        )
        transport = IPBlockerTransport(wrapped=wrapped)
        await transport.handle_async_request(
            httpx.Request("GET", "https://93.184.216.34/bar")
        )
        sent: httpx.Request = wrapped.handle_async_request.call_args[0][0]
        assert sent.url.host == "93.184.216.34"
        assert sent.url.path == "/bar"

    @pytest.mark.asyncio
    async def test_blocked_ip_raises(self) -> None:
        with patch(
            "port_ocean.helpers.ip_blocker._resolve_to_ip_addresses",
            return_value=["127.0.0.1"],
        ):
            wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = IPBlockerTransport(wrapped=wrapped)
            with pytest.raises(BlockedIPError) as exc_info:
                await transport.handle_async_request(
                    httpx.Request("GET", "https://evil.local/")
                )
            assert "127.0.0.1" in str(exc_info.value)
            wrapped.handle_async_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolve_empty_raises(self) -> None:
        with patch(
            "port_ocean.helpers.ip_blocker._resolve_to_ip_addresses", return_value=[]
        ):
            wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = IPBlockerTransport(wrapped=wrapped)
            with pytest.raises(BlockedIPError) as exc_info:
                await transport.handle_async_request(
                    httpx.Request("GET", "https://nonexistent.invalid/")
                )
            assert "could not resolve" in str(exc_info.value).lower()
            wrapped.handle_async_request.assert_not_awaited()
