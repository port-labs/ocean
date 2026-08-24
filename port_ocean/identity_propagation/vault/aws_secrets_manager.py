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
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        super().__init__(secret_prefix)
        self._region_name = region_name
        self._endpoint_url = endpoint_url
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._boto_client: Any = None

    @property
    def _client(self) -> Any:
        if self._boto_client is None:
            # Explicit kwargs, even when None, take priority over AWS_PROFILE/SSO in boto3's
            # default credential chain — passing them here is what lets a developer point this
            # at LocalStack without touching an unrelated AWS_PROFILE they need for other work.
            logger.info(
                "Constructing Secrets Manager vault client",
                endpoint=self._endpoint_url or "default AWS endpoint",
                region=self._region_name,
                explicit_credentials=self._aws_access_key_id is not None,
            )
            self._boto_client = boto3.client(
                "secretsmanager",
                region_name=self._region_name,
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._aws_access_key_id,
                aws_secret_access_key=self._aws_secret_access_key,
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
