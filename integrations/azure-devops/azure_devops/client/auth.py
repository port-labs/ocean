import base64
import os
from typing import Any, Protocol

from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential


ADO_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"


class AuthProvider(Protocol):
    auth_description: str

    async def get_auth_headers(self) -> dict[str, str]: ...


class PatAuthProvider:
    auth_description = "PAT (Personal Access Token)"

    def __init__(self, pat: str) -> None:
        self._pat = pat

    async def get_auth_headers(self) -> dict[str, str]:
        encoded = base64.b64encode(f":{self._pat}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}


class ServicePrincipalAuthProvider:
    auth_description = "Service Principal credentials"

    def __init__(self, credential: AsyncTokenCredential) -> None:
        self._credential = credential

    async def get_auth_headers(self) -> dict[str, str]:
        token = (await self._credential.get_token(ADO_SCOPE)).token
        return {"Authorization": f"Bearer {token}"}


ACCOUNT_MODE_SINGLE = "Single Account"
ACCOUNT_MODE_MULTIPLE = "Multiple Accounts"


def build_auth_provider(config: dict[str, Any]) -> AuthProvider:
    account_mode = config.get("account_mode", ACCOUNT_MODE_SINGLE)

    if account_mode == ACCOUNT_MODE_MULTIPLE:
        for field in ("client_id", "client_secret", "tenant_id"):
            if not config.get(field):
                raise ValueError(
                    f"Service Principal auth requires '{field}'. "
                    "Provide clientId, clientSecret, and tenantId."
                )
        os.environ["AZURE_TENANT_ID"] = config["tenant_id"]
        os.environ["AZURE_CLIENT_ID"] = config["client_id"]
        os.environ["AZURE_CLIENT_SECRET"] = config["client_secret"]
        return ServicePrincipalAuthProvider(DefaultAzureCredential())

    if account_mode == ACCOUNT_MODE_SINGLE:
        pat = config.get("personal_access_token")
        if not pat:
            raise ValueError("PAT auth requires 'personal_access_token'.")
        return PatAuthProvider(pat)

    raise ValueError(
        f"Unknown account_mode: '{account_mode}'. "
        "Expected 'Single Account' (PAT) or 'Multiple Accounts' (Service Principal)."
    )
