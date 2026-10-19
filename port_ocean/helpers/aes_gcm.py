"""aes256-gcm framing matching Port `@port-labs/schema-validator` encrypted inputs.

Wire format: base64(iv[16] || ciphertext || authTag[16]).
Key material: first 32 UTF-8 bytes of the org client secret.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def decrypt_aes256_gcm(secret: str, encoded: str) -> str:
    raw = base64.b64decode(encoded)
    iv, ciphertext, tag = raw[:16], raw[16:-16], raw[-16:]
    key = secret[:32].encode("utf-8")
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
    return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")


def encrypt_aes256_gcm(secret: str, plaintext: str) -> str:
    """Round-trip helper; production encrypt lives in workflow-service."""
    iv = os.urandom(16)
    key = secret[:32].encode("utf-8")
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv)).encryptor()
    ciphertext = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext + encryptor.tag).decode("ascii")
