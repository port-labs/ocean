from __future__ import annotations

import base64
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.utils.misc import get_spec_file


def decrypt_aes256_gcm(secret: str, encoded: str) -> str:
    raw = base64.b64decode(encoded)
    iv, ciphertext, tag = raw[:16], raw[16:-16], raw[-16:]
    key = secret[:32].encode("utf-8")
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
    return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")


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


def resolve_port_mcp_url(api_base_url: str) -> str:
    """Map a Port API base URL to the matching Port MCP URL (always normalized)."""
    parsed = urlparse(api_base_url)
    if not parsed.hostname or not parsed.hostname.startswith("api."):
        return "https://mcp.port.io/v1"
    hostname = f"mcp.{parsed.hostname.removeprefix('api.')}"
    netloc = f"{hostname}:{parsed.port}" if parsed.port else hostname
    return f"{parsed.scheme or 'https'}://{netloc}/v1".rstrip("/")


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
    if not isinstance(run, WorkflowNodeRun) or not isinstance(
        run.execution_identity, dict
    ):
        return None

    identity = run.execution_identity
    identity_type = identity.get("type")
    allowed = _allowed_execution_identities(run.action_type)
    if identity_type not in allowed:
        raise ActionExecutionError(
            f'executionIdentity type "{identity_type}" is not allowed for'
            f" {run.action_type}"
        )
    if not isinstance(identity.get("identifier"), str):
        raise ActionExecutionError("executionIdentity must include identifier")

    access_token = decrypt_run_access_token(run)
    if not access_token:
        raise ActionExecutionError(
            "portAccessToken is required when executionIdentity is set"
        )
    return access_token
