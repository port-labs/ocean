import asyncio

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.exceptions.identity_propagation import (
    IdentityPropagationError,
    OAuthError,
    OAuthProviderNotConfiguredError,
    UserAuthRequiredError,
    VaultError,
)
from port_ocean.identity_propagation.oauth_broker.providers import require_provider
from port_ocean.identity_propagation.vault.base import TokenRecord, VaultClient
from port_ocean.identity_propagation.verifier import IdentityClaims

# Serializes refresh per stored secret. Two runs for the same user and target
# would otherwise refresh at once and, because providers rotate refresh tokens,
# leave the loser holding one the provider has already invalidated.
_refresh_locks: dict[str, asyncio.Lock] = {}


def _require_vault() -> VaultClient:
    vault = ocean.app.vault_client
    if vault is None:
        raise ActionExecutionError(
            "Vault client is not configured. Set ocean.app.vault_client during integration startup."
        )
    return vault


async def resolve_user_token(run: IntegrationRun) -> str | None:
    """Return the user's downstream access token, or None for non-identity runs."""
    if not isinstance(run, WorkflowNodeRun) or not run.identity_token:
        return None

    if not ocean.config.identity_propagation.enabled:
        raise ActionExecutionError(
            "Run requires identity propagation but it is not enabled on this integration"
        )

    try:
        provider = require_provider()
    except OAuthProviderNotConfiguredError as e:
        raise ActionExecutionError(str(e)) from e

    # This process's own identity, not `run.integration_config.integrationProvider` — Ocean
    # always verifies/stores as itself rather than trusting a caller-supplied field. One
    # process hosts exactly one integration, so there's nothing to look up.
    target = provider.target

    logger.debug(
        "Resolving user token for identity-propagated run",
        node_run_id=run.id,
        target=target,
    )

    try:
        claims = await ocean.app.identity_verifier.verify(run.identity_token, target)
    except IdentityPropagationError as e:
        raise ActionExecutionError(f"Identity token verification failed: {e}") from e

    vault = _require_vault()
    record = await _read(vault, claims, target)
    if record is None:
        logger.info(
            "No vault record for this user/target — pausing for reauth",
            org_id=claims.org_id,
            actor=claims.sub,
            target=target,
        )
        raise UserAuthRequiredError()

    if record.is_expired():
        logger.debug("Stored token expired, refreshing", actor=claims.sub, target=target)
        record = await _refresh(vault, claims, target, record)

    return record.access_token


async def _read(
    vault: VaultClient, claims: IdentityClaims, target: str
) -> TokenRecord | None:
    try:
        return await vault.read(claims.org_id, claims.sub, target)
    except VaultError as e:
        raise ActionExecutionError(f"Could not read the user's token: {e}") from e


async def _refresh(
    vault: VaultClient, claims: IdentityClaims, target: str, record: TokenRecord
) -> TokenRecord:
    """Renew an expired token, degrading to re-auth if refresh is not possible."""
    if not record.refresh_token:
        raise UserAuthRequiredError()

    secret_name = vault.secret_name(claims.org_id, claims.sub, target)
    lock = _refresh_locks.setdefault(secret_name, asyncio.Lock())
    async with lock:
        current = await _read(vault, claims, target)
        if current is not None and not current.is_expired():
            return current
        if current is None or not current.refresh_token:
            raise UserAuthRequiredError()

        provider = require_provider()

        try:
            refreshed = await provider.refresh(current.refresh_token)
        except OAuthError as e:
            logger.info(
                "Token refresh rejected, asking the user to re-authenticate",
                target=target,
                secret_name=secret_name,
                error=str(e),
            )
            raise UserAuthRequiredError() from e

        try:
            await vault.write(claims.org_id, claims.sub, target, refreshed)
        except VaultError as e:
            logger.warning(
                "Refreshed token could not be stored; the next run will refresh again",
                target=target,
                secret_name=secret_name,
                error=str(e),
            )

        logger.info("Refreshed the user's token", target=target, run_id=claims.run_id)
        return refreshed
