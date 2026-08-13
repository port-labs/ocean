import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.identity_propagation.vault.aws_secrets_manager import AWSSecretsManagerVaultClient
from port_ocean.identity_propagation.vault.base import TokenRecord
from port_ocean.exceptions.identity_propagation import VaultError


class ResourceNotFoundException(Exception):
    pass


class ResourceExistsException(Exception):
    pass


@pytest.fixture
def mock_boto_client() -> MagicMock:
    client = MagicMock()
    client.exceptions.ResourceNotFoundException = ResourceNotFoundException
    client.exceptions.ResourceExistsException = ResourceExistsException
    return client


@pytest.fixture
def vault_client(mock_boto_client: MagicMock) -> AWSSecretsManagerVaultClient:
    with patch(
        "port_ocean.clients.vault.aws_secrets_manager.boto3.client",
        return_value=mock_boto_client,
    ):
        client = AWSSecretsManagerVaultClient(region_name="eu-west-1")
        # Materialize the lazy client while the patch is active.
        assert client._client is mock_boto_client
        return client


def test_secret_name_namespaces_by_org_and_actor(
    vault_client: AWSSecretsManagerVaultClient,
) -> None:
    assert (
        vault_client.secret_name("org_1", "jane@acme.com", "github")
        == "port/tokens/org_1/jane@acme.com/github"
    )


async def test_read_returns_the_stored_record(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    mock_boto_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "access_token": "gho_token",
                "refresh_token": "ghr_token",
                "expires_at": 1720000000,
            }
        )
    }

    record = await vault_client.read("org_1", "jane", "github")

    assert record is not None
    assert record.access_token == "gho_token"
    assert record.refresh_token == "ghr_token"
    assert record.expires_at == 1720000000
    mock_boto_client.get_secret_value.assert_called_once_with(
        SecretId="port/tokens/org_1/jane/github"
    )


async def test_read_treats_a_missing_secret_as_a_miss(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    mock_boto_client.get_secret_value.side_effect = ResourceNotFoundException()

    assert await vault_client.read("org_1", "jane", "github") is None


async def test_read_raises_on_an_unexpected_failure(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    mock_boto_client.get_secret_value.side_effect = Exception("access denied")

    with pytest.raises(VaultError):
        await vault_client.read("org_1", "jane", "github")


async def test_read_raises_on_a_malformed_record(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    mock_boto_client.get_secret_value.return_value = {"SecretString": "not json"}

    with pytest.raises(VaultError):
        await vault_client.read("org_1", "jane", "github")


async def test_write_creates_the_secret_on_first_use(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    record = TokenRecord(access_token="gho_token", expires_at=1720000000)

    await vault_client.write("org_1", "jane", "github", record)

    _, kwargs = mock_boto_client.create_secret.call_args
    assert kwargs["Name"] == "port/tokens/org_1/jane/github"
    assert json.loads(kwargs["SecretString"]) == {
        "access_token": "gho_token",
        "expires_at": 1720000000,
    }
    mock_boto_client.put_secret_value.assert_not_called()


async def test_write_updates_an_existing_secret(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    mock_boto_client.create_secret.side_effect = ResourceExistsException()
    record = TokenRecord(access_token="gho_new", refresh_token="ghr_new")

    await vault_client.write("org_1", "jane", "github", record)

    _, kwargs = mock_boto_client.put_secret_value.call_args
    assert kwargs["SecretId"] == "port/tokens/org_1/jane/github"
    assert json.loads(kwargs["SecretString"])["access_token"] == "gho_new"


async def test_write_raises_when_the_vault_rejects_it(
    vault_client: AWSSecretsManagerVaultClient, mock_boto_client: MagicMock
) -> None:
    mock_boto_client.create_secret.side_effect = Exception("access denied")

    with pytest.raises(VaultError):
        await vault_client.write(
            "org_1", "jane", "github", TokenRecord(access_token="gho_token")
        )


@pytest.mark.parametrize(
    "expires_at, expected",
    [(None, False), (2_000_000_000, False), (1_000_000_000, True)],
)
def test_is_expired(expires_at: Any, expected: bool) -> None:
    assert TokenRecord(access_token="t", expires_at=expires_at).is_expired() is expected
