import asyncio
import time
from abc import ABC, abstractmethod
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from loguru import logger
from pydantic.v1 import BaseModel, ValidationError

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.identity_propagation import (
    IdentityVerificationError,
    IdentityVerifierNotAvailableError,
)
from port_ocean.utils import http_async_client

VERIFY_RUN_PATH = "/workflows/identity/verify-run"
DISCOVERY_PATH = "/.well-known/openid-configuration"
# `iss` is read off the token before its signature is checked, so it decides which JWKS is
# allowed to vouch for the token. Anything outside Port's own domains is rejected: otherwise a
# token pointing at an attacker-hosted JWKS would verify against the attacker's own key.
TRUSTED_ISSUER_HOST_SUFFIXES = (".getport.io", ".port.io")
# How long to trust a resolved JWKS URI before re-running discovery. Key rotation within
# the JWKS itself is handled separately by PyJWKClient's own cache.
DISCOVERY_CACHE_TTL_SECONDS = 3600


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
    """Verifies identity tokens via OIDC discovery against the issuer named in the token."""

    def __init__(self) -> None:
        self._jwks_client: PyJWKClient | None = None
        self._resolved_issuer: str | None = None
        self._jwks_client_resolved_at: float = 0.0

    async def _resolve_jwks_client(self, issuer_url: str) -> PyJWKClient:
        is_stale = (
            self._jwks_client is None
            or self._resolved_issuer != issuer_url
            or time.monotonic() - self._jwks_client_resolved_at
            > DISCOVERY_CACHE_TTL_SECONDS
        )
        if is_stale:
            response = await http_async_client.get(
                f"{issuer_url.rstrip('/')}{DISCOVERY_PATH}"
            )
            response.raise_for_status()
            jwks_uri = response.json()["jwks_uri"]
            self._jwks_client = PyJWKClient(jwks_uri)
            self._resolved_issuer = issuer_url
            self._jwks_client_resolved_at = time.monotonic()
        assert self._jwks_client is not None
        return self._jwks_client

    @staticmethod
    def _read_unverified_issuer(token: str) -> str:
        # A JWT payload is base64, not encrypted, so `iss` is readable without a key. The
        # signature is checked below against the JWKS that this issuer publishes.
        try:
            issuer = jwt.decode(token, options={"verify_signature": False}).get("iss")
        except jwt.PyJWTError as e:
            raise IdentityVerificationError(
                f"Could not read the identity token: {e}"
            ) from e

        if not issuer:
            raise IdentityVerificationError("Identity token has no iss claim")
        return issuer

    @staticmethod
    def _assert_trusted_issuer(issuer_url: str) -> None:
        host = urlparse(issuer_url).hostname or ""
        # The configured Port API host is trusted too, which covers deployments that serve the
        # JWKS from the API domain and local setups where both run on localhost.
        api_host = urlparse(ocean.port_client.api_url).hostname or ""
        if host and (host == api_host or host.endswith(TRUSTED_ISSUER_HOST_SUFFIXES)):
            return

        logger.warning(
            "Rejected an identity token from an untrusted issuer", issuer=issuer_url
        )
        raise IdentityVerificationError(
            f"Identity token issuer {issuer_url} is not a Port issuer"
        )

    async def verify(self, token: str, expected_target: str) -> IdentityClaims:
        issuer_url = self._read_unverified_issuer(token)
        self._assert_trusted_issuer(issuer_url)

        try:
            jwks_client = await self._resolve_jwks_client(issuer_url)
            # PyJWKClient does its own blocking HTTP + key-cache lookup by kid.
            signing_key = await asyncio.to_thread(
                jwks_client.get_signing_key_from_jwt, token
            )
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=expected_target,
                issuer=issuer_url,
            )
        except jwt.PyJWTError as e:
            raise IdentityVerificationError(
                f"Identity token verification failed: {e}"
            ) from e
        except Exception as e:
            raise IdentityVerificationError(
                f"Could not verify identity token: {e}"
            ) from e

        try:
            return IdentityClaims(
                sub=payload["sub"],
                org_id=payload["org_id"],
                run_id=payload["run_id"],
                node_run_id=payload.get("node_run_id"),
                actor_email=payload.get("actor_email"),
            )
        except (KeyError, ValidationError) as e:
            raise IdentityVerificationError(
                f"Malformed identity token payload: {e}"
            ) from e

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
