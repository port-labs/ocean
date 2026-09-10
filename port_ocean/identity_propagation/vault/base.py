import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic.v1 import BaseModel

if TYPE_CHECKING:
    from port_ocean.config.settings import VaultSettings

DEFAULT_SECRET_PREFIX = "port/tokens"
# Renew slightly early so a token cannot expire between the check and its use.
EXPIRY_LEEWAY_SECONDS = 60


class TokenRecord(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: int | None = None

    def is_expired(self, leeway_seconds: int = EXPIRY_LEEWAY_SECONDS) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - leeway_seconds


class VaultClient(ABC):

    def __init__(self, secret_prefix: str = DEFAULT_SECRET_PREFIX) -> None:
        self._secret_prefix = secret_prefix.strip("/")

    def secret_name(self, org_id: str, actor_id: str, target: str) -> str:
        return f"{self._secret_prefix}/{org_id}/{actor_id}/{target}"

    @abstractmethod
    async def read(self, org_id: str, actor_id: str, target: str) -> TokenRecord | None:
        """Return the stored record, or None when nothing is stored yet."""

    @abstractmethod
    async def write(
        self, org_id: str, actor_id: str, target: str, record: TokenRecord
    ) -> None:
        """Store the record, creating the secret on first write."""


def build_vault_client(settings: "VaultSettings") -> "VaultClient | None":
    from port_ocean.config.settings import AWSSecretsManagerVaultSettings, VaultType

    if settings.type == VaultType.aws_secrets_manager:
        from port_ocean.identity_propagation.vault.aws_secrets_manager import (
            AWSSecretsManagerVaultClient,
        )

        # `vault`'s declared field type is the base VaultSettings, so env-parsed values land as
        # a plain VaultSettings instance even when they include AWS-specific keys (kept as extra
        # attributes via Extra.allow). Rebuild from the full dict rather than isinstance-branching,
        # or aws_region/endpoint_url/credentials silently get dropped.
        aws_settings = (
            settings
            if isinstance(settings, AWSSecretsManagerVaultSettings)
            else AWSSecretsManagerVaultSettings.parse_obj(settings.dict())
        )
        return AWSSecretsManagerVaultClient(
            region_name=aws_settings.aws_region,
            secret_prefix=aws_settings.secret_prefix,
            endpoint_url=aws_settings.endpoint_url,
            aws_access_key_id=aws_settings.aws_access_key_id,
            aws_secret_access_key=aws_settings.aws_secret_access_key,
        )
    return None  # custom: caller sets ocean.app.vault_client
