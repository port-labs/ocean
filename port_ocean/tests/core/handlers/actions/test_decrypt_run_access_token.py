from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.handlers.actions.utils import _decrypt_run_access_token
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

_ORG_SECRET = "x" * 40


def _workflow_run(*, port_access_token: str | None) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="wfnr_1",
        node_uid="wfn_1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        port_access_token=port_access_token,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="inst",
            integrationProvider="claude-managed-agents",
            integrationInvocationType="trigger_agent",
            integrationActionExecutionProperties={},
        ),
    )


def test_decrypt_run_access_token_requires_token() -> None:
    with pytest.raises(ActionExecutionError, match="portAccessToken is required"):
        _decrypt_run_access_token(_workflow_run(port_access_token=None))


def test_decrypt_run_access_token_decrypts_ciphertext() -> None:
    plaintext = "port.access.token"
    ciphertext = encrypt_aes256_gcm(_ORG_SECRET, plaintext)
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret=_ORG_SECRET)

    with patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean):
        assert _decrypt_run_access_token(
            _workflow_run(port_access_token=ciphertext)
        ) == (plaintext)


def test_decrypt_run_access_token_fails_on_wrong_secret() -> None:
    ciphertext = encrypt_aes256_gcm(_ORG_SECRET, "tok")
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret="y" * 40)

    with (
        patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean),
        pytest.raises(ActionExecutionError, match="decrypt portAccessToken"),
    ):
        _decrypt_run_access_token(_workflow_run(port_access_token=ciphertext))
