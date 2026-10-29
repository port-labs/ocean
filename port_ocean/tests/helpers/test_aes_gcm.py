from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm
from port_ocean.utils.aes_gcm import decrypt_aes256_gcm


def test_aes256_gcm_round_trip() -> None:
    secret = "a" * 40
    plaintext = "port.access.token.value"
    encoded = encrypt_aes256_gcm(secret, plaintext)
    assert encoded != plaintext
    assert decrypt_aes256_gcm(secret, encoded) == plaintext


def test_aes256_gcm_wrong_secret_fails() -> None:
    encoded = encrypt_aes256_gcm("a" * 32, "secret-token")
    try:
        decrypt_aes256_gcm("b" * 32, encoded)
        raise AssertionError("expected decrypt failure")
    except Exception:
        pass
