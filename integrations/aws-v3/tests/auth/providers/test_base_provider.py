import pytest
from typing import Any, Type
from aiobotocore.session import AioSession
from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.web_identity_provider import WebIdentityCredentialProvider


ALL_PROVIDERS = [
    StaticCredentialProvider,
    AssumeRoleProvider,
    WebIdentityCredentialProvider,
]
PROVIDER_REFRESHABLE = [
    (StaticCredentialProvider, False),
    (AssumeRoleProvider, True),
    (WebIdentityCredentialProvider, False),
]


class TestCredentialProviderBase:
    """Test base CredentialProvider contract."""

    @pytest.mark.parametrize("config", [{"key": "value"}, {}, None])
    def test_initialization(self, config: Any) -> None:
        """Base initialization works with any config."""
        provider = StaticCredentialProvider(config=config)
        assert provider.config == (config or {})
        assert isinstance(provider.aws_client_factory_session, AioSession)


class TestProviderContract:
    """Test all providers follow the contract."""

    @pytest.mark.parametrize("provider_class,expected", PROVIDER_REFRESHABLE)
    def test_is_refreshable(
        self, provider_class: Type[CredentialProvider], expected: bool
    ) -> None:
        """All providers implement is_refreshable correctly."""
        assert provider_class().is_refreshable == expected

    @pytest.mark.parametrize("provider_class", ALL_PROVIDERS)
    def test_interface_compliance(
        self, provider_class: Type[CredentialProvider]
    ) -> None:
        """All providers implement required interface."""
        provider = provider_class()
        assert isinstance(provider, CredentialProvider)
        assert callable(provider.get_credentials)
        assert callable(provider.get_session)
        assert hasattr(provider, "is_refreshable")
