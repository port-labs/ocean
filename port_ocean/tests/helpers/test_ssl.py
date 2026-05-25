import ssl
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from port_ocean.config.settings import IntegrationConfiguration, PortSettings
from port_ocean.helpers import async_client as async_client_module
from port_ocean.helpers.ssl import (
    SSLClientType,
    _create_httpx_default_ssl_context,
    get_ssl_context,
)


class RecordingTransport(httpx.AsyncBaseTransport):
    captured_kwargs: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        self.__class__.captured_kwargs = kwargs

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request)


def test_ssl_settings_are_loaded_from_ocean_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCEAN__PORT_VERIFY_SSL", "false")
    monkeypatch.setenv("OCEAN__PORT_DISABLE_STRICT_SSL_VERIFICATION", "true")
    monkeypatch.setenv("OCEAN__THIRD_PARTY_VERIFY_SSL", "false")
    monkeypatch.setenv("OCEAN__THIRD_PARTY_DISABLE_STRICT_SSL_VERIFICATION", "true")

    config = IntegrationConfiguration(
        port=PortSettings(client_id="client-id", client_secret="client-secret")
    )

    assert config.port_verify_ssl is False
    assert config.port_disable_strict_ssl_verification is True
    assert config.third_party_verify_ssl is False
    assert config.third_party_disable_strict_ssl_verification is True


def test_get_ssl_context_uses_port_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "port_ocean.helpers.ssl.ocean",
        SimpleNamespace(
            config=SimpleNamespace(
                port_verify_ssl=False,
                port_disable_strict_ssl_verification=False,
            )
        ),
    )

    assert get_ssl_context(SSLClientType.PORT) is False


def test_get_ssl_context_uses_third_party_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "port_ocean.helpers.ssl.ocean",
        SimpleNamespace(
            config=SimpleNamespace(
                third_party_verify_ssl=False,
                third_party_disable_strict_ssl_verification=False,
            )
        ),
    )

    assert get_ssl_context(SSLClientType.THIRD_PARTY) is False


def test_get_ssl_context_can_disable_strict_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "port_ocean.helpers.ssl.ocean",
        SimpleNamespace(
            config=SimpleNamespace(
                port_verify_ssl=True,
                port_disable_strict_ssl_verification=True,
            )
        ),
    )

    context = get_ssl_context(SSLClientType.PORT)

    assert isinstance(context, ssl.SSLContext)
    assert not context.verify_flags & ssl.VERIFY_X509_STRICT


def test_create_httpx_default_ssl_context_uses_certifi_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}
    original_create_default_context = ssl.create_default_context

    def create_default_context(**kwargs: Any) -> ssl.SSLContext:
        captured_kwargs.update(kwargs)
        return original_create_default_context()

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    monkeypatch.setattr(
        "port_ocean.helpers.ssl.ssl.create_default_context",
        create_default_context,
    )
    monkeypatch.setattr("port_ocean.helpers.ssl.certifi.where", lambda: "/certifi.pem")

    _create_httpx_default_ssl_context()

    assert captured_kwargs == {"cafile": "/certifi.pem"}


def test_create_httpx_default_ssl_context_prefers_ssl_cert_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}
    original_create_default_context = ssl.create_default_context

    def create_default_context(**kwargs: Any) -> ssl.SSLContext:
        captured_kwargs.update(kwargs)
        return original_create_default_context()

    monkeypatch.setenv("SSL_CERT_FILE", "/custom/cert-file.pem")
    monkeypatch.setenv("SSL_CERT_DIR", "/custom/cert-dir")
    monkeypatch.setattr(
        "port_ocean.helpers.ssl.ssl.create_default_context",
        create_default_context,
    )

    _create_httpx_default_ssl_context()

    assert captured_kwargs == {"cafile": "/custom/cert-file.pem"}


def test_create_httpx_default_ssl_context_uses_ssl_cert_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}
    original_create_default_context = ssl.create_default_context

    def create_default_context(**kwargs: Any) -> ssl.SSLContext:
        captured_kwargs.update(kwargs)
        return original_create_default_context()

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setenv("SSL_CERT_DIR", "/custom/cert-dir")
    monkeypatch.setattr(
        "port_ocean.helpers.ssl.ssl.create_default_context",
        create_default_context,
    )

    _create_httpx_default_ssl_context()

    assert captured_kwargs == {"capath": "/custom/cert-dir"}


@pytest.mark.asyncio
async def test_ocean_async_client_defaults_to_third_party_ssl_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        async_client_module.httpx,
        "AsyncHTTPTransport",
        RecordingTransport,
    )
    monkeypatch.setattr(
        async_client_module.OceanAsyncClient,
        "_wrap_with_ip_blocker_if_needed",
        lambda _, transport: transport,
    )
    monkeypatch.setattr(
        async_client_module,
        "get_ssl_context",
        lambda client_type: client_type == SSLClientType.PORT,
    )

    client = async_client_module.OceanAsyncClient(trust_env=False)
    await client.aclose()

    assert RecordingTransport.captured_kwargs["verify"] is False


@pytest.mark.asyncio
async def test_ocean_async_client_keeps_explicit_verify_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        async_client_module.httpx,
        "AsyncHTTPTransport",
        RecordingTransport,
    )
    monkeypatch.setattr(
        async_client_module.OceanAsyncClient,
        "_wrap_with_ip_blocker_if_needed",
        lambda _, transport: transport,
    )
    monkeypatch.setattr(
        async_client_module,
        "get_ssl_context",
        lambda _: pytest.fail("explicit verify should not resolve default SSL config"),
    )

    client = async_client_module.OceanAsyncClient(verify=True, trust_env=False)
    await client.aclose()

    assert RecordingTransport.captured_kwargs["verify"] is True
