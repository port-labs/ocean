import asyncio
import json
from typing import Any

import boto3
from loguru import logger

from port_ocean.identity_propagation.vault.base import (
    DEFAULT_SECRET_PREFIX,
    TokenRecord,
    VaultClient,
)
from port_ocean.exceptions.identity_propagation import VaultError


class AWSSecretsManagerVaultClient(VaultClient):

    def __init__(
        self,
        region_name: str | None = None,
        secret_prefix: str = DEFAULT_SECRET_PREFIX,
    ) -> None:
        super().__init__(secret_prefix)
        self._region_name = region_name
        self._boto_client: Any = None

    @property
    def _client(self) -> Any:
        if self._boto_client is None:
            self._boto_client = boto3.client(
                "secretsmanager", region_name=self._region_name
            )
        return self._boto_client

    async def read(self, org_id: str, actor_id: str, target: str) -> TokenRecord | None:
        secret_name = self.secret_name(org_id, actor_id, target)
        try:
            response = await asyncio.to_thread(
                self._client.get_secret_value, SecretId=secret_name
            )
        except self._client.exceptions.ResourceNotFoundException:
            logger.info("No stored token for this user", secret_name=secret_name)
            return None
        except Exception as e:
            raise VaultError(f"Failed to read secret '{secret_name}': {e}") from e

        try:
            return TokenRecord.parse_obj(json.loads(response["SecretString"]))
        except Exception as e:
            raise VaultError(f"Malformed token record in '{secret_name}': {e}") from e

    async def write(
        self, org_id: str, actor_id: str, target: str, record: TokenRecord
    ) -> None:
        secret_name = self.secret_name(org_id, actor_id, target)
        secret_string = record.json(exclude_none=True)
        try:
            try:
                await asyncio.to_thread(
                    self._client.create_secret,
                    Name=secret_name,
                    SecretString=secret_string,
                )
            except self._client.exceptions.ResourceExistsException:
                await asyncio.to_thread(
                    self._client.put_secret_value,
                    SecretId=secret_name,
                    SecretString=secret_string,
                )
        except Exception as e:
            raise VaultError(f"Failed to write secret '{secret_name}': {e}") from e

        logger.info("Stored token for this user", secret_name=secret_name)
