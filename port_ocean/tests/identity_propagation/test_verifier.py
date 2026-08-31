import time
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from port_ocean.exceptions.identity_propagation import (
    IdentityVerificationError,
    IdentityVerifierNotAvailableError,
)
from port_ocean.identity_propagation import verifier as verifier_module
from port_ocean.identity_propagation.verifier import (
    PortIdentityTokenVerifier,
    UnavailableIdentityTokenVerifier,
)

ISSUER_URL = "https://identity.getport.io"
API_URL = "https://api.getport.io/v1"
JWKS_URI = f"{ISSUER_URL}/.well-known/jwks.json"


def response(status_code: int = 200, body: object = None) -> MagicMock:
    return MagicMock(status_code=status_code, json=MagicMock(return_value=body or {}))


@pytest.fixture(scope="module")
def signing_key() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def identity_token(
    signing_key: RSAPrivateKey, issuer: str = ISSUER_URL, target: str = "github"
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "jane@acme.com",
            "org_id": "org_1",
            "run_id": "run_1",
            "node_run_id": "node_run_1",
            "actor_email": "jane@acme.com",
            "iss": issuer,
            "aud": target,
            "iat": now,
            "exp": now + 300,
        },
        signing_key,
        algorithm="RS256",
    )


@pytest.fixture(autouse=True)
def mock_http_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    mock = MagicMock()
    mock.get = AsyncMock(return_value=response())
    monkeypatch.setattr(verifier_module, "http_async_client", mock)
    yield mock


@pytest.fixture(autouse=True)
def mock_ocean(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    mock = MagicMock()
    # The issuer comes from the token, not from here. api_url is still where verify_run_actor
    # goes, and it doubles as an additional trusted issuer host.
    mock.port_client.api_url = API_URL
    mock.port_client.auth.headers = AsyncMock(
        return_value={"Authorization": "Bearer token"}
    )
    monkeypatch.setattr(verifier_module, "ocean", mock)
    yield mock


async def test_verify_fails_closed() -> None:
    with pytest.raises(IdentityVerifierNotAvailableError):
        await UnavailableIdentityTokenVerifier().verify("any.jwt.token", "github")


async def test_verify_run_actor_fails_closed() -> None:
    with pytest.raises(IdentityVerifierNotAvailableError):
        await UnavailableIdentityTokenVerifier().verify_run_actor(
            "run_1", "jane@acme.com", "org_1"
        )


async def test_verify_run_actor_returns_the_org_reported_by_port(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.get.return_value = response(
        body={"active": True, "actorId": "jane@acme.com", "orgId": "org_1"}
    )

    org_id = await PortIdentityTokenVerifier().verify_run_actor(
        "run_1", "jane@acme.com", "attacker_org"
    )

    assert org_id == "org_1"


async def test_verify_run_actor_rejects_when_port_omits_org_id(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.get.return_value = response(
        body={"active": True, "actorId": "jane@acme.com"}
    )

    with pytest.raises(IdentityVerificationError):
        await PortIdentityTokenVerifier().verify_run_actor(
            "run_1", "jane@acme.com", "attacker_org"
        )


async def test_verify_run_actor_rejects_someone_who_did_not_trigger_the_run(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.get.return_value = response(
        body={"active": True, "actorId": "jane@acme.com", "orgId": "org_1"}
    )

    with pytest.raises(IdentityVerificationError):
        await PortIdentityTokenVerifier().verify_run_actor(
            "run_1", "mallory@acme.com", "org_1"
        )


async def test_verify_run_actor_rejects_a_run_that_is_no_longer_active(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.get.return_value = response(
        body={"active": False, "actorId": None, "orgId": "org_1"}
    )

    with pytest.raises(IdentityVerificationError):
        await PortIdentityTokenVerifier().verify_run_actor(
            "run_1", "jane@acme.com", "org_1"
        )


async def test_verify_run_actor_fails_closed_when_port_is_unreachable(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.get.return_value = response(status_code=500)

    with pytest.raises(IdentityVerificationError):
        await PortIdentityTokenVerifier().verify_run_actor(
            "run_1", "jane@acme.com", "org_1"
        )


@pytest.fixture
def mock_jwks_client(
    monkeypatch: pytest.MonkeyPatch, signing_key: RSAPrivateKey
) -> Iterator[MagicMock]:
    client = MagicMock()
    client.get_signing_key_from_jwt = MagicMock(
        return_value=MagicMock(key=signing_key.public_key())
    )
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(verifier_module, "PyJWKClient", factory)
    yield factory


async def test_verify_discovers_the_jwks_from_the_token_issuer(
    mock_http_client: MagicMock,
    mock_jwks_client: MagicMock,
    signing_key: RSAPrivateKey,
) -> None:
    mock_http_client.get.return_value = response(body={"jwks_uri": JWKS_URI})

    claims = await PortIdentityTokenVerifier().verify(
        identity_token(signing_key), "github"
    )

    assert claims.org_id == "org_1"
    assert claims.run_id == "run_1"
    mock_http_client.get.assert_awaited_once_with(
        f"{ISSUER_URL}{verifier_module.DISCOVERY_PATH}"
    )
    mock_jwks_client.assert_called_once_with(JWKS_URI)


async def test_verify_rejects_an_issuer_outside_port(
    mock_http_client: MagicMock, signing_key: RSAPrivateKey
) -> None:
    token = identity_token(signing_key, issuer="https://evil.example.com")

    with pytest.raises(IdentityVerificationError):
        await PortIdentityTokenVerifier().verify(token, "github")

    # Rejected before discovery, so the attacker's JWKS is never fetched.
    mock_http_client.get.assert_not_awaited()


async def test_verify_rejects_a_token_without_an_issuer(
    signing_key: RSAPrivateKey,
) -> None:
    token = jwt.encode({"sub": "jane@acme.com"}, signing_key, algorithm="RS256")

    with pytest.raises(IdentityVerificationError):
        await PortIdentityTokenVerifier().verify(token, "github")
