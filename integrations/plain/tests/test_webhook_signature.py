from plain.webhook_signature import verify_plain_signature


def test_valid_signature_is_accepted() -> None:
    body = b'{"type":"thread.thread_created","payload":{}}'
    secret = "test-secret"
    import hashlib
    import hmac

    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert (
        verify_plain_signature(
            body,
            {"Plain-Request-Signature": signature},
            secret,
        )
        is True
    )


def test_invalid_signature_is_rejected() -> None:
    assert (
        verify_plain_signature(
            b"{}",
            {"Plain-Request-Signature": "deadbeef"},
            "test-secret",
        )
        is False
    )


def test_missing_signature_is_rejected_when_secret_configured() -> None:
    assert verify_plain_signature(b"{}", {}, "test-secret") is False


def test_missing_secret_skips_verification() -> None:
    assert verify_plain_signature(b"{}", {}, None) is True
