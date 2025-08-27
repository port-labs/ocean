from aws.auth import (
    AssumeRoleProvider,
    AssumeRoleWithWebIdentityProvider,
    CredentialProvider,
    CredentialsProviderError,
    MultiAccountStrategy,
    OrganizationsStrategy,
    RegionResolver,
    ResyncStrategyFactory,
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
    "ResyncStrategyFactory",
    "SingleAccountStrategy",
    "StaticCredentialProvider",
]
