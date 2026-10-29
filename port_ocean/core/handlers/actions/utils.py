from __future__ import annotations

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.utils.aes_gcm import decrypt_aes256_gcm
from port_ocean.utils.misc import get_spec_file


def _decrypt_run_access_token(run: IntegrationRun) -> str:
    if not isinstance(run, WorkflowNodeRun) or not run.port_access_token:
        raise ActionExecutionError(
            "portAccessToken is required when decrypting a run access token"
        )

    try:
        return decrypt_aes256_gcm(
            ocean.config.port.client_secret, run.port_access_token
        )
    except Exception as error:
        raise ActionExecutionError(
            "Failed to decrypt portAccessToken (org clientSecret mismatch?)"
        ) from error


def _allowed_execution_identities(action_type: str) -> list[str]:
    spec = get_spec_file()
    if not isinstance(spec, dict):
        return []
    for action in spec.get("actions") or []:
        if isinstance(action, dict) and action.get("name") == action_type:
            allowed = action.get("allowedExecutionIdentities") or []
            return [item for item in allowed if isinstance(item, str)]
    return []


def get_run_access_token(run: IntegrationRun) -> str | None:
    """Decrypt portAccessToken when the run has an execution identity.

    No executionIdentity → None.
    Identity present but invalid / missing token → ActionExecutionError.
    """
    if not isinstance(run, WorkflowNodeRun) or run.execution_identity is None:
        return None

    identity = run.execution_identity
    allowed = _allowed_execution_identities(run.action_type)
    if identity.type not in allowed:
        raise ActionExecutionError(
            f'executionIdentity type "{identity.type}" is not allowed for'
            f" {run.action_type}"
        )

    return _decrypt_run_access_token(run)
