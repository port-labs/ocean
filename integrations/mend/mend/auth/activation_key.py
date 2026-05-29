import base64
from urllib.parse import urlparse
from typing import Any
import jwt
from loguru import logger

from mend.exceptions import MendAuthenticationError

_CAESAR_OFFSET = 4
_INVALID_KEY_MESSAGE = ("Provide a valid Mend Activation key.")


def _caesar_cipher_decrypt(activation_key: str) -> str:
    decrypted = "".join(chr(ord(c) - _CAESAR_OFFSET) for c in activation_key)
    reversed_str = decrypted[::-1]
    return base64.b64decode(reversed_str).decode("utf-8")


def decode_activation_key(activation_key: str) -> dict[str, Any]:
    if not isinstance(activation_key, str) or not activation_key:
        raise MendAuthenticationError(_INVALID_KEY_MESSAGE)
    try:
        license_key = _caesar_cipher_decrypt(activation_key)
        return jwt.decode(license_key, options={"verify_signature": False})
    except (ValueError, TypeError, jwt.PyJWTError) as e:
        logger.debug(f"Failed to decode Mend activation key: {type(e).__name__}: {e}")
        raise MendAuthenticationError(_INVALID_KEY_MESSAGE) from e


def derive_base_url(ws_env_url: str) -> str:
    parsed = urlparse(ws_env_url)
    hostname = parsed.hostname or ws_env_url
    return f"https://api-{hostname}"
