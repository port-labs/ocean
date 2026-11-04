from __future__ import annotations

from typing import Any

from clients.auth.default_credential_authenticator import (
    DefaultAzureCredentialAuthenticator,
)
from clients.auth.service_principal_authenticator import ServicePrincipalAuthenticator


def create_authenticator(config: dict[str, Any]):
    authenticator = ServicePrincipalAuthenticator.from_integration_config(config)
    if authenticator is None:
        authenticator = DefaultAzureCredentialAuthenticator()
    return authenticator
