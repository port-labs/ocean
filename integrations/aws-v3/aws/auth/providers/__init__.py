from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.web_identity_provider import WebIdentityCredentialProvider

__all__ = [
    "CredentialProvider",
    "StaticCredentialProvider",
    "AssumeRoleProvider",
    "WebIdentityCredentialProvider",
]
