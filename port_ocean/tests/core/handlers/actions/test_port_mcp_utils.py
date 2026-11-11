from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import (
    ResolvedExecutionIdentity,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

_ORG_SECRET = "x" * 40
_TRIGGER_AGENT_SPEC = {
    "actions": [
        {
            "name": "trigger_agent",
            "allowedExecutionIdentities": ["actor", "service_account"],
        }
    ]
}


def _workflow_run(
    *,
    port_access_token: str | None,
    execution_identity: ResolvedExecutionIdentity | None,
) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="wfnr_1",
        node_uid="wfn_1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        port_access_token=port_access_token,
        execution_identity=execution_identity,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="inst",
            integrationProvider="claude-managed-agents",
            integrationInvocationType="trigger_agent",
            integrationActionExecutionProperties={},
        ),
    )


def test_get_run_access_token_returns_none_without_identity() -> None:
    assert (
        get_run_access_token(
            _workflow_run(port_access_token=None, execution_identity=None)
        )
        is None
    )


def test_get_run_access_token_decrypts_token() -> None:
    plaintext = "port.access.token"
    ciphertext = encrypt_aes256_gcm(_ORG_SECRET, plaintext)
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret=_ORG_SECRET)

    with (
        patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean),
        patch(
            "port_ocean.core.handlers.actions.utils.get_spec_file",
            return_value=_TRIGGER_AGENT_SPEC,
        ),
    ):
        token = get_run_access_token(
            _workflow_run(
                port_access_token=ciphertext,
                execution_identity=ResolvedExecutionIdentity(
                    type="actor",
                    identifier="user@example.com",
                ),
            )
        )

    assert token == plaintext


def test_get_run_access_token_requires_token_when_identity_set() -> None:
    with (
        patch(
            "port_ocean.core.handlers.actions.utils.get_spec_file",
            return_value=_TRIGGER_AGENT_SPEC,
        ),
        pytest.raises(ActionExecutionError, match="portAccessToken"),
    ):
        get_run_access_token(
            _workflow_run(
                port_access_token=None,
                execution_identity=ResolvedExecutionIdentity(
                    type="actor",
                    identifier="user@example.com",
                ),
            )
        )


def test_get_run_access_token_rejects_identity_not_in_spec_allowlist() -> None:
    with (
        patch(
            "port_ocean.core.handlers.actions.utils.get_spec_file",
            return_value={
                "actions": [
                    {
                        "name": "trigger_agent",
                        "allowedExecutionIdentities": ["service_account"],
                    }
                ]
            },
        ),
        pytest.raises(ActionExecutionError, match="not allowed"),
    ):
        get_run_access_token(
            _workflow_run(
                port_access_token="tok",
                execution_identity=ResolvedExecutionIdentity(
                    type="actor",
                    identifier="user@example.com",
                ),
            )
        )
