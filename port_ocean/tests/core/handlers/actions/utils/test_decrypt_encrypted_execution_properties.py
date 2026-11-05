from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.handlers.actions.utils import (
    decrypt_encrypted_execution_properties,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

_ORG_SECRET = "x" * 40


def _workflow_run(
    *,
    properties: dict[str, object],
    encrypted_properties: list[str] | None,
) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="wfnr_1",
        node_uid="wfn_1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        encrypted_properties=encrypted_properties,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="inst",
            integrationProvider="github",
            integrationInvocationType="dispatch_workflow",
            integrationActionExecutionProperties=properties,
        ),
    )


def test_decrypt_encrypted_execution_properties_noop_for_action_run() -> None:
    run = ActionRun(
        id="ar_1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="a"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst",
            integrationActionType="dispatch_workflow",
            integrationActionExecutionProperties={"token": "plain"},
        ),
    )
    decrypt_encrypted_execution_properties(run)
    assert run.execution_properties["token"] == "plain"


def test_decrypt_encrypted_execution_properties_noop_without_hint() -> None:
    run = _workflow_run(
        properties={"repo": "ocean"},
        encrypted_properties=None,
    )
    decrypt_encrypted_execution_properties(run)
    assert run.execution_properties == {"repo": "ocean"}


def test_decrypt_encrypted_execution_properties_decrypts_listed_leaves() -> None:
    plaintext_token = "super-secret"
    plaintext_auth = "Bearer super-secret"
    run = _workflow_run(
        properties={
            "api_token": encrypt_aes256_gcm(_ORG_SECRET, plaintext_token),
            "authorization": encrypt_aes256_gcm(_ORG_SECRET, plaintext_auth),
            "repo": "ocean",
        },
        encrypted_properties=["api_token", "authorization"],
    )
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret=_ORG_SECRET)

    with patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean):
        decrypt_encrypted_execution_properties(run)

    assert run.execution_properties == {
        "api_token": plaintext_token,
        "authorization": plaintext_auth,
        "repo": "ocean",
    }
    assert run.encrypted_properties == ["api_token", "authorization"]


def test_decrypt_encrypted_execution_properties_skips_missing_optional_value() -> None:
    run = _workflow_run(
        properties={"repo": "ocean"},
        encrypted_properties=["api_token"],
    )
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret=_ORG_SECRET)

    with patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean):
        decrypt_encrypted_execution_properties(run)

    assert run.execution_properties == {"repo": "ocean"}


def test_decrypt_encrypted_execution_properties_skips_null_optional_value() -> None:
    run = _workflow_run(
        properties={"api_token": None, "repo": "ocean"},
        encrypted_properties=["api_token"],
    )
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret=_ORG_SECRET)

    with patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean):
        decrypt_encrypted_execution_properties(run)

    assert run.execution_properties == {"api_token": None, "repo": "ocean"}


def test_decrypt_encrypted_execution_properties_rejects_non_string_value() -> None:
    run = _workflow_run(
        properties={"api_token": 123},
        encrypted_properties=["api_token"],
    )
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret=_ORG_SECRET)

    with (
        patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean),
        pytest.raises(
            ActionExecutionError,
            match='Encrypted property "api_token" must be a string',
        ),
    ):
        decrypt_encrypted_execution_properties(run)


def test_decrypt_encrypted_execution_properties_wrong_secret() -> None:
    run = _workflow_run(
        properties={
            "api_token": encrypt_aes256_gcm(_ORG_SECRET, "tok"),
        },
        encrypted_properties=["api_token"],
    )
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(client_secret="y" * 40)

    with (
        patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean),
        pytest.raises(
            ActionExecutionError, match="Failed to decrypt execution property"
        ),
    ):
        decrypt_encrypted_execution_properties(run)
