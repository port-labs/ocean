import pytest
from typing import Any

from azure_integration.factory import (
    AzureAuthenticatorFactory,
    create_azure_client,
    AzureClientType,
)
from azure_integration.helpers.exceptions import MissingAzureCredentials
from azure_integration.clients.rest.rest_client import AzureRestClient


def test_azure_authenticator_factory_requires_credentials() -> None:
    with pytest.raises(MissingAzureCredentials):
        AzureAuthenticatorFactory.create(
            tenant_id="", client_id="abc", client_secret="def"
        )


def test_create_azure_client_returns_rest_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Avoid requiring azure.identity by faking the credential
    class _DummyCred:
        async def get_token(self, *args: Any, **kwargs: Any) -> Any:
            class _Tok:
                token = "t"

            return _Tok()

    monkeypatch.setattr(
        AzureAuthenticatorFactory, "create", staticmethod(lambda **_: _DummyCred())
    )

    client = create_azure_client(AzureClientType.REST)
    assert isinstance(client, AzureRestClient)
