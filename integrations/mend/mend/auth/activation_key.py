import base64
from urllib.parse import urlparse
from typing import Any
import jwt
from loguru import logger

from mend.exceptions import MendAuthenticationError

_CAESAR_OFFSET = 4
_INVALID_KEY_MESSAGE = "Provide a valid Mend Activation key."

# The decoded JWT payload must carry these for the integration to work
# (see initialize_client.py). Validated here so a malformed key fails at
# decode time with a precise clue instead of a KeyError later on.
_REQUIRED_PAYLOAD_FIELDS = ("integratorEmail", "userKey", "wsEnvUrl", "orgUuid")


def _caesar_cipher_decrypt(activation_key: str) -> str:
    decrypted = "".join(chr(ord(c) - _CAESAR_OFFSET) for c in activation_key)
    reversed_str = decrypted[::-1]
    return base64.b64decode(reversed_str).decode("utf-8")


def decode_activation_key(activation_key: str) -> dict[str, Any]:
    """Decode a Mend activation key into its credential payload.

    The key format mirrors Mend's own scheme (Caesar shift + reverse +
    base64 wrapping an unsigned JWT). Each stage logs its failure at DEBUG
    — never the key itself — so a format change on Mend's side can be
    pinpointed from the logs.
    """
    if not isinstance(activation_key, str) or not activation_key:
        raise MendAuthenticationError(_INVALID_KEY_MESSAGE)

    try:
        license_key = _caesar_cipher_decrypt(activation_key)
    except (ValueError, TypeError) as e:
        logger.debug(
            "Mend activation key deobfuscation failed "
            f"(Caesar/reverse/base64 stage): {type(e).__name__}: {e}"
        )
        raise MendAuthenticationError(_INVALID_KEY_MESSAGE) from e

    try:
        payload: dict[str, Any] = jwt.decode(
            license_key, options={"verify_signature": False}
        )
    except (ValueError, TypeError, jwt.PyJWTError) as e:
        logger.debug(f"Mend activation key JWT parsing failed: {type(e).__name__}: {e}")
        raise MendAuthenticationError(_INVALID_KEY_MESSAGE) from e

    missing = [field for field in _REQUIRED_PAYLOAD_FIELDS if not payload.get(field)]
    if missing:
        # Field names are not secrets; payload values are never logged.
        logger.debug(
            f"Mend activation key payload is missing fields: {', '.join(missing)}"
        )
        raise MendAuthenticationError(
            f"{_INVALID_KEY_MESSAGE} The key payload is missing: {', '.join(missing)}."
        )

    return payload


def derive_base_url(ws_env_url: str) -> str:
    parsed = urlparse(ws_env_url)
    hostname = parsed.hostname or ws_env_url
    return f"https://api-{hostname}"
