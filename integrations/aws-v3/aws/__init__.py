from aws.auth import (
    AssumeRoleProvider,
    AssumeRoleWithWebIdentityProvider,
    CredentialProvider,
    CredentialsProviderError,
    MultiAccountStrategy,
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
    "RegionResolver",
    "ResyncStrategyFactory",
    "SingleAccountStrategy",
    "StaticCredentialProvider",
]
