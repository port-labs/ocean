from abc import ABC, abstractmethod

from loguru import logger
from pydantic.v1 import BaseModel

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.identity_propagation import (
    IdentityVerificationError,
    IdentityVerifierNotAvailableError,
)
from port_ocean.utils import http_async_client

VERIFY_RUN_PATH = "/workflows/identity/verify-run"


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


class PortIdentityTokenVerifier(IdentityTokenVerifier):
    """
    Verifies identity tokens against the JWKS that Port serves alongside the workflow API.

    Port currently issues these tokens from an in-process stub whose signing key lives in
    memory, so a Port restart invalidates every token already in flight. Once the Identity
    Service ships, only the issuer moves - this verifier keeps working unchanged.
    """

    async def verify(self, token: str, expected_target: str) -> IdentityClaims:
        # TODO(identity-propagation): implement real OIDC identity token verification.
        # This needs to:
        #   1. Fetch the JWKS from the production identity issuer (cache with a TTL,
        #      keyed by `kid`, and refresh on cache miss/expiry - see the removed
        #      _signing_key/_refresh_keys logic in git history for a starting point).
        #   2. Verify the token's RS256 signature against the matching JWK.
        #   3. Validate standard claims: `exp` (not expired), `aud` (matches
        #      `expected_target`), and `iss` (matches the trusted issuer).
        #   4. Map the verified payload onto `IdentityClaims`, raising
        #      `IdentityVerificationError` for malformed tokens, unknown signing
        #      keys, or missing required claims (`sub`, `org_id`, `run_id`).
        # This is intentionally left unimplemented here; a production-ready
        # implementation is being built as a separate workstream.
        raise NotImplementedError(
            "TODO: implement real OIDC identity token verification against a "
            "production JWKS endpoint"
        )

    async def verify_run_actor(
        self, run_id: str, actor_id: str, org_id: str | None = None
    ) -> str:
        response = await http_async_client.get(
            f"{ocean.port_client.api_url}{VERIFY_RUN_PATH}",
            params={"runId": run_id},
            headers=await self._headers(),
        )
        if response.status_code >= 400:
            raise IdentityVerificationError(
                f"Could not confirm the run's actor with Port (HTTP {response.status_code})"
            )

        body = response.json()
        if not body.get("active"):
            raise IdentityVerificationError(
                "This workflow run is no longer waiting for authentication"
            )

        run_actor = body.get("actorId")
        if not run_actor or run_actor.casefold() != actor_id.casefold():
            logger.warning(
                "Rejected an authorize request from someone other than the run's actor",
                run_id=run_id,
            )
            raise IdentityVerificationError(
                "Only the user who triggered this run can authenticate for it"
            )

        # Trust Port's org over the caller-supplied one: the query param is attacker-controllable
        # and decides which vault namespace the token lands in.
        return body.get("orgId") or org_id or ""

    @staticmethod
    async def _headers() -> dict[str, str]:
        return {
            **await ocean.port_client.auth.headers(),
            "x-port-reserved-usage": "true",
        }
