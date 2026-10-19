from __future__ import annotations

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.helpers.aes_gcm import decrypt_aes256_gcm


def decrypt_run_access_token(run: IntegrationRun) -> str | None:
    if not isinstance(run, WorkflowNodeRun) or not run.port_access_token:
        return None

    try:
        return decrypt_aes256_gcm(
            ocean.config.port.client_secret, run.port_access_token
        )
    except Exception as error:
        raise ActionExecutionError(
            "Failed to decrypt portAccessToken (org clientSecret mismatch?)"
        ) from error
