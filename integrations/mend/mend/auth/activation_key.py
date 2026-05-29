import base64
from urllib.parse import urlparse
from typing import Any
import jwt

_CAESAR_OFFSET = 4


def _caesar_cipher_decrypt(activation_key: str) -> str:
    decrypted = "".join(chr(ord(c) - _CAESAR_OFFSET) for c in activation_key)
    reversed_str = decrypted[::-1]
    return base64.b64decode(reversed_str).decode("utf-8")


def decode_activation_key(activation_key: str) -> dict[str, Any]:
    license_key = _caesar_cipher_decrypt(activation_key)
    return jwt.decode(license_key, options={"verify_signature": False})


def derive_base_url(ws_env_url: str) -> str:
    parsed = urlparse(ws_env_url)
    hostname = parsed.hostname or ws_env_url
    return f"https://api-{hostname}"
