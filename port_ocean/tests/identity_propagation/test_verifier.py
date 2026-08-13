import pytest

from port_ocean.identity_propagation.verifier import UnavailableIdentityTokenVerifier
from port_ocean.exceptions.identity_propagation import IdentityVerifierNotAvailableError


async def test_verify_fails_closed() -> None:
    with pytest.raises(IdentityVerifierNotAvailableError):
        await UnavailableIdentityTokenVerifier().verify("any.jwt.token", "github")


async def test_verify_run_actor_fails_closed() -> None:
    with pytest.raises(IdentityVerifierNotAvailableError):
        await UnavailableIdentityTokenVerifier().verify_run_actor(
            "run_1", "jane@acme.com", "org_1"
        )
