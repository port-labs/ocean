import os

import pytest
from typing import Any

from azure.identity.aio import DefaultAzureCredential

from azure_integration.factory import (
    AzureAuthenticatorFactory,
    create_azure_client,
    AzureClientType,
)
from azure_integration.clients.rest.rest_client import AzureRestClient


def test_returns_default_credential_when_all_provided() -> None:
    credential = AzureAuthenticatorFactory.create(
        tenant_id="tenant", client_id="client", client_secret="secret"
    )
    assert isinstance(credential, DefaultAzureCredential)


def test_returns_default_credential_when_secret_missing() -> None:
    credential = AzureAuthenticatorFactory.create(
        tenant_id="tenant", client_id="client", client_secret=None
    )
    assert isinstance(credential, DefaultAzureCredential)


def test_returns_default_credential_when_all_none() -> None:
    credential = AzureAuthenticatorFactory.create()
    assert isinstance(credential, DefaultAzureCredential)


def test_sets_env_vars_when_credentials_provided() -> None:
    AzureAuthenticatorFactory.create(
        tenant_id="test-tenant", client_id="test-client", client_secret="test-secret"
    )
    assert os.environ.get("AZURE_TENANT_ID") == "test-tenant"
    assert os.environ.get("AZURE_CLIENT_ID") == "test-client"
    assert os.environ.get("AZURE_CLIENT_SECRET") == "test-secret"


def test_does_not_set_env_vars_when_none() -> None:
    for key in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        os.environ.pop(key, None)
    AzureAuthenticatorFactory.create()
    assert "AZURE_CLIENT_SECRET" not in os.environ


def test_create_azure_client_returns_rest_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyCred:
        async def get_token(self, *args: Any, **kwargs: Any) -> Any:
            class _Tok:
                token = "t"

            return _Tok()

    monkeypatch.setattr(
        AzureAuthenticatorFactory, "create", staticmethod(lambda *_, **__: _DummyCred())
    )

    client = create_azure_client(AzureClientType.RESOURCE_MANAGER)
    assert isinstance(client, AzureRestClient)
