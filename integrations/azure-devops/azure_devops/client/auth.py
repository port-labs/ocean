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


def build_auth_provider(config: dict[str, Any]) -> AuthProvider:
    has_pat = bool(config.get("personal_access_token"))
    has_sp = bool(config.get("client_id"))

    if has_pat and has_sp:
        raise ValueError(
            "Both PAT and Service Principal credentials are configured. "
            "Use one authentication method, not both."
        )

    if has_sp:
        for field in ("client_id", "client_secret", "tenant_id"):
            if not config.get(field):
                raise ValueError(
                    f"Service Principal auth requires '{field}'. "
                    "Provide clientId, clientSecret, and tenantId."
                )
        if config.get("tenant_id"):
            os.environ["AZURE_TENANT_ID"] = config["tenant_id"]
        if config.get("client_id"):
            os.environ["AZURE_CLIENT_ID"] = config["client_id"]
        if config.get("client_secret"):
            os.environ["AZURE_CLIENT_SECRET"] = config["client_secret"]
        return ServicePrincipalAuthProvider(DefaultAzureCredential())

    if has_pat:
        return PatAuthProvider(config["personal_access_token"])

    raise ValueError(
        "No authentication configured. Provide either "
        "personalAccessToken (PAT) or Service Principal credentials "
        "(clientId, clientSecret, tenantId)."
    )
