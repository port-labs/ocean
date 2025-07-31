from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.assume_role_with_web_identity_provider import (
    AssumeRoleWithWebIdentityProvider,
)
from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.static_provider import StaticCredentialProvider

__all__ = [
    "CredentialProvider",
    "StaticCredentialProvider",
    "AssumeRoleProvider",
    "AssumeRoleWithWebIdentityProvider",
]
