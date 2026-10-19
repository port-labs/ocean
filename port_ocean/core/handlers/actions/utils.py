from __future__ import annotations

import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


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
