from aws.auth import (
    AssumeRoleProvider,
    AssumeRoleWithWebIdentityProvider,
    CredentialProvider,
    CredentialsProviderError,
    MultiAccountStrategy,
    OrganizationsStrategy,
    RegionResolver,
    AccountStrategyFactory,
    SingleAccountStrategy,
    StaticCredentialProvider,
)

__all__ = [
    "AssumeRoleProvider",
    "AssumeRoleWithWebIdentityProvider",
    "CredentialProvider",
    "CredentialsProviderError",
    "MultiAccountStrategy",
    "OrganizationsStrategy",
    "RegionResolver",
    "AccountStrategyFactory",
    "SingleAccountStrategy",
    "StaticCredentialProvider",
]
