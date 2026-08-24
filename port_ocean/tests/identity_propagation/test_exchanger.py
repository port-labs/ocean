import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.identity_propagation import token_exchanger as exchanger
from port_ocean.identity_propagation.token_exchanger import resolve_user_token
from port_ocean.identity_propagation.verifier import IdentityClaims
from port_ocean.identity_propagation.vault.base import TokenRecord, VaultClient
from port_ocean.core.models import (
    ActionRun,
    ActionRunStatus,
    IntegrationActionInvocationPayload,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.exceptions.identity_propagation import (
    UserAuthRequiredError,
    IdentityVerificationError,
    OAuthError,
    VaultError,
)

CLAIMS = IdentityClaims(
    sub="jane@acme.com", org_id="org_1", run_id="run_1", node_run_id="node_run_1"
)
EXPIRED_AT = int(time.time()) - 3600
VALID_UNTIL = int(time.time()) + 3600


def generate_identity_run(
    identity_token: str | None = "identity.jwt.token",
) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="test-wf-node-run-id",
        node_uid="test-node-uid",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="github",
            integrationInvocationType="test_action",
            integrationActionExecutionProperties={},
        ),
        output={},
        identity_token=identity_token,
    )


def generate_action_run() -> ActionRun:
    return ActionRun(
        id="test-run-id",
        status=ActionRunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="test-action-identifier"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationActionType="test_action",
            integrationActionExecutionProperties={},
        ),
    )


@pytest.fixture
def mock_vault() -> MagicMock:
    vault = MagicMock(spec=VaultClient)
    vault.read = AsyncMock(return_value=None)
    vault.write = AsyncMock()
    vault.secret_name = MagicMock(return_value="port/tokens/org_1/jane@acme.com/github")
    return vault


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.target = "github"
    provider.refresh = AsyncMock()
    return provider


@pytest.fixture(autouse=True)
def identity_environment(
    monkeypatch: pytest.MonkeyPatch, mock_vault: MagicMock, mock_provider: MagicMock
) -> None:
    verifier = MagicMock()
    verifier.verify = AsyncMock(return_value=CLAIMS)

    mock_ocean = MagicMock()
    mock_ocean.config.identity_propagation.enabled = True
    mock_ocean.app.vault_client = mock_vault
    mock_ocean.app.identity_verifier = verifier

    monkeypatch.setattr(exchanger, "ocean", mock_ocean)
    monkeypatch.setattr(exchanger, "require_provider", lambda: mock_provider)
    exchanger._refresh_locks.clear()


async def test_returns_none_for_a_run_without_an_identity_token(
    mock_vault: MagicMock,
) -> None:
    assert await resolve_user_token(generate_identity_run(identity_token=None)) is None
    mock_vault.read.assert_not_called()


async def test_returns_none_for_an_action_run(mock_vault: MagicMock) -> None:
    assert await resolve_user_token(generate_action_run()) is None
    mock_vault.read.assert_not_called()


async def test_returns_the_stored_token_on_a_vault_hit(mock_vault: MagicMock) -> None:
    mock_vault.read.return_value = TokenRecord(
        access_token="gho_live", expires_at=VALID_UNTIL
    )

    assert await resolve_user_token(generate_identity_run()) == "gho_live"
    mock_vault.read.assert_awaited_once_with("org_1", "jane@acme.com", "github")


async def test_vault_miss_asks_the_user_to_authenticate(mock_vault: MagicMock) -> None:
    mock_vault.read.return_value = None

    with pytest.raises(UserAuthRequiredError):
        await resolve_user_token(generate_identity_run())


async def test_expired_token_without_a_refresh_token_asks_for_re_auth(
    mock_vault: MagicMock, mock_provider: MagicMock
) -> None:
    mock_vault.read.return_value = TokenRecord(
        access_token="gho_stale", expires_at=EXPIRED_AT
    )

    with pytest.raises(UserAuthRequiredError):
        await resolve_user_token(generate_identity_run())

    mock_provider.refresh.assert_not_called()


async def test_expired_token_is_refreshed_and_the_rotated_record_stored(
    mock_vault: MagicMock, mock_provider: MagicMock
) -> None:
    mock_vault.read.return_value = TokenRecord(
        access_token="gho_stale", refresh_token="ghr_old", expires_at=EXPIRED_AT
    )
    mock_provider.refresh.return_value = TokenRecord(
        access_token="gho_fresh", refresh_token="ghr_rotated", expires_at=VALID_UNTIL
    )

    assert await resolve_user_token(generate_identity_run()) == "gho_fresh"

    mock_provider.refresh.assert_awaited_once_with("ghr_old")
    written = mock_vault.write.await_args.args[3]
    assert written.access_token == "gho_fresh"
    assert written.refresh_token == "ghr_rotated"


async def test_a_rejected_refresh_asks_for_re_auth_rather_than_failing_the_run(
    mock_vault: MagicMock, mock_provider: MagicMock
) -> None:
    mock_vault.read.return_value = TokenRecord(
        access_token="gho_stale", refresh_token="ghr_revoked", expires_at=EXPIRED_AT
    )
    mock_provider.refresh.side_effect = OAuthError("invalid_grant")

    with pytest.raises(UserAuthRequiredError):
        await resolve_user_token(generate_identity_run())


async def test_a_refreshed_token_is_used_even_if_it_cannot_be_stored(
    mock_vault: MagicMock, mock_provider: MagicMock
) -> None:
    mock_vault.read.return_value = TokenRecord(
        access_token="gho_stale", refresh_token="ghr_old", expires_at=EXPIRED_AT
    )
    mock_provider.refresh.return_value = TokenRecord(access_token="gho_fresh")
    mock_vault.write.side_effect = VaultError("write denied")

    assert await resolve_user_token(generate_identity_run()) == "gho_fresh"


async def test_concurrent_runs_refresh_only_once(
    mock_vault: MagicMock, mock_provider: MagicMock
) -> None:
    stored = TokenRecord(
        access_token="gho_stale", refresh_token="ghr_old", expires_at=EXPIRED_AT
    )
    refreshed = TokenRecord(
        access_token="gho_fresh", refresh_token="ghr_rotated", expires_at=VALID_UNTIL
    )

    async def read(*_: Any) -> TokenRecord:
        return stored

    async def refresh(_: str) -> TokenRecord:
        # Yield, so a second caller would slip in were the lock not held.
        await asyncio.sleep(0)
        return refreshed

    async def write(*args: Any) -> None:
        nonlocal stored
        stored = args[3]

    mock_vault.read.side_effect = read
    mock_vault.write.side_effect = write
    mock_provider.refresh.side_effect = refresh

    tokens = await asyncio.gather(
        resolve_user_token(generate_identity_run()),
        resolve_user_token(generate_identity_run()),
    )

    assert tokens == ["gho_fresh", "gho_fresh"]
    assert mock_provider.refresh.await_count == 1


async def test_an_invalid_identity_token_fails_the_run(
    monkeypatch: pytest.MonkeyPatch, mock_vault: MagicMock
) -> None:
    verifier = MagicMock()
    verifier.verify = AsyncMock(side_effect=IdentityVerificationError("bad signature"))
    mock_ocean = MagicMock()
    mock_ocean.config.identity_propagation.enabled = True
    mock_ocean.app.vault_client = mock_vault
    mock_ocean.app.identity_verifier = verifier
    monkeypatch.setattr(exchanger, "ocean", mock_ocean)

    with pytest.raises(ActionExecutionError):
        await resolve_user_token(generate_identity_run())

    mock_vault.read.assert_not_called()


async def test_an_identity_run_on_a_disabled_integration_fails_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.config.identity_propagation.enabled = False
    monkeypatch.setattr(exchanger, "ocean", mock_ocean)

    with pytest.raises(ActionExecutionError):
        await resolve_user_token(generate_identity_run())


async def test_an_unreadable_vault_fails_the_run(mock_vault: MagicMock) -> None:
    mock_vault.read.side_effect = VaultError("access denied")

    with pytest.raises(ActionExecutionError):
        await resolve_user_token(generate_identity_run())


async def test_a_disabled_integration_is_never_consulted_for_a_plain_run(
    mock_vault: MagicMock,
) -> None:
    assert await resolve_user_token(generate_action_run()) is None
    mock_vault.read.assert_not_called()
