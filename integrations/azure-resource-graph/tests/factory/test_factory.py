import pytest
from typing import Any

from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential

from azure_integration.factory import (
    AzureAuthenticatorFactory,
    create_azure_client,
    AzureClientType,
)
from azure_integration.clients.rest.rest_client import AzureRestClient


def test_returns_client_secret_credential_when_all_provided() -> None:
    credential = AzureAuthenticatorFactory.create(
        tenant_id="tenant", client_id="client", client_secret="secret"
    )
    assert isinstance(credential, ClientSecretCredential)


def test_returns_default_credential_when_secret_missing() -> None:
    credential = AzureAuthenticatorFactory.create(
        tenant_id="tenant", client_id="client", client_secret=None
    )
    assert isinstance(credential, DefaultAzureCredential)


def test_returns_default_credential_when_all_none() -> None:
    credential = AzureAuthenticatorFactory.create()
    assert isinstance(credential, DefaultAzureCredential)


def test_returns_default_credential_when_tenant_missing() -> None:
    credential = AzureAuthenticatorFactory.create(
        tenant_id=None, client_id="client", client_secret="secret"
    )
    assert isinstance(credential, DefaultAzureCredential)


def test_create_azure_client_returns_rest_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyCred:
        async def get_token(self, *args: Any, **kwargs: Any) -> Any:
            class _Tok:
                token = "t"

            return _Tok()

    monkeypatch.setattr(
        AzureAuthenticatorFactory, "create", staticmethod(lambda **_: _DummyCred())
    )

    client = create_azure_client(AzureClientType.RESOURCE_MANAGER)
    assert isinstance(client, AzureRestClient)
