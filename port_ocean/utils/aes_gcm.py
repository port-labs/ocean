from __future__ import annotations

import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def decrypt_aes256_gcm(secret: str, encoded: str) -> str:
    raw = base64.b64decode(encoded)
    iv, ciphertext, tag = raw[:16], raw[16:-16], raw[-16:]
    key = secret[:32].encode("utf-8")
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
    return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")
