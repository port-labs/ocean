from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest

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


def response(status_code: int = 200, body: object = None) -> MagicMock:
    return MagicMock(status_code=status_code, json=MagicMock(return_value=body or {}))


@pytest.fixture(autouse=True)
def mock_http_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    mock = MagicMock()
    mock.get = AsyncMock(return_value=response())
    monkeypatch.setattr(verifier_module, "http_async_client", mock)
    yield mock


@pytest.fixture(autouse=True)
def mock_ocean(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    mock = MagicMock()
    # Ocean's own Port API URL doubles as the trusted OIDC issuer - no separate config,
    # same pattern as verify_run_actor.
    mock.port_client.api_url = ISSUER_URL
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
