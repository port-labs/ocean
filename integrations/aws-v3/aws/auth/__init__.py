from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.assume_role_with_web_identity_provider import (
    AssumeRoleWithWebIdentityProvider,
)
from aws.auth.session_factory import AccountStrategyFactory
from aws.auth.strategies.base import AWSSessionStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.organizations_strategy import OrganizationsStrategy
from aws.auth.region_resolver import RegionResolver
from aws.auth.utils import CredentialsProviderError

__all__ = [
    "CredentialProvider",
    "StaticCredentialProvider",
    "AssumeRoleProvider",
    "AssumeRoleWithWebIdentityProvider",
    "CredentialsProviderError",
    "AccountStrategyFactory",
    "AWSSessionStrategy",
    "SingleAccountStrategy",
    "MultiAccountStrategy",
    "OrganizationsStrategy",
    "RegionResolver",
]
