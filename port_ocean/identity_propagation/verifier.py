from abc import ABC, abstractmethod

from pydantic.v1 import BaseModel

from port_ocean.exceptions.identity_propagation import IdentityVerifierNotAvailableError


class IdentityClaims(BaseModel):
    sub: str
    org_id: str
    run_id: str
    node_run_id: str | None = None
    actor_email: str | None = None


class IdentityTokenVerifier(ABC):

    @abstractmethod
    async def verify(self, token: str, expected_target: str) -> IdentityClaims:
        """Return the claims of a valid token, or raise IdentityVerificationError."""

    @abstractmethod
    async def verify_run_actor(
        self, run_id: str, actor_id: str, org_id: str | None = None
    ) -> str:
        """Confirm the actor owns the run and return the run's org, or raise IdentityVerificationError."""


class UnavailableIdentityTokenVerifier(IdentityTokenVerifier):

    async def verify(self, token: str, expected_target: str) -> IdentityClaims:
        raise IdentityVerifierNotAvailableError(
            "Identity token verification is not available in this Ocean version"
        )

    async def verify_run_actor(
        self, run_id: str, actor_id: str, org_id: str | None = None
    ) -> str:
        raise IdentityVerifierNotAvailableError(
            "Identity token verification is not available in this Ocean version"
        )
