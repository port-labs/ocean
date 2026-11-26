import hashlib
import hmac

from langfuse.webhook.signature import verify_langfuse_signature


def test_verify_langfuse_signature_valid() -> None:
    secret = "whsec"
    body = '{"id":"1"}'
    timestamp = "1720701136"
    digest = hmac.new(
        secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
    ).hexdigest()
    header = f"t={timestamp},v1={digest}"
    assert verify_langfuse_signature(body, header, secret) is True


def test_verify_langfuse_signature_invalid() -> None:
    assert verify_langfuse_signature('{"id":"1"}', "t=1,v1=deadbeef", "whsec") is False


def test_verify_langfuse_signature_bad_header() -> None:
    assert verify_langfuse_signature("{}", "not-a-header", "whsec") is False
