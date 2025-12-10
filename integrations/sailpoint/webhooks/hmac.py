import hashlib
import hmac


def verify_hmac(secret: str, payload: bytes, signature: str) -> bool:
    mac = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature.replace("sha256=", ""))
