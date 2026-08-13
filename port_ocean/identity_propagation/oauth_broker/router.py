from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.identity_propagation import (
    IdentityVerifierNotAvailableError,
    IdentityVerificationError,
    OAuthError,
    VaultError,
)
from port_ocean.identity_propagation.oauth_broker.providers import (
    PROVIDER_DEFAULTS,
    OAuth2Provider,
)
from port_ocean.identity_propagation.oauth_broker.state import (
    InvalidStateError,
    sign_state,
    verify_state,
)
from port_ocean.utils import http_async_client

OAUTH_CALLBACK_PATH = "/v1/oauth-broker/callback"


def _redirect_uri() -> str:
    return f"{ocean.app.base_url}{OAUTH_CALLBACK_PATH}"


def _resume_api_url(run_id: str, node_run_id: str) -> str:
    return f"{ocean.port_client.api_url}/workflows/runs/{run_id}/resume?nodeRunId={node_run_id}"


def _run_view_url(run_id: str) -> str:
    # Derive the Port app URL from the API URL (api.getport.io → app.getport.io).
    api_url = ocean.port_client.api_url.rstrip("/")
    app_url = api_url.replace("api.", "app.").removesuffix("/v1")
    return f"{app_url}/runs/{run_id}"


def _require_provider(target: str) -> OAuth2Provider:
    settings = getattr(
        ocean.config.identity_propagation.oauth, target.replace("-", "_"), None
    )
    if settings is None or target not in PROVIDER_DEFAULTS:
        raise HTTPException(
            status_code=404, detail=f"No OAuth provider configured for '{target}'"
        )
    return OAuth2Provider(target, settings)


async def _verify_actor(run_id: str, actor_id: str, org_id: str | None) -> str:
    try:
        return await ocean.app.identity_verifier.verify_run_actor(
            run_id, actor_id, org_id
        )
    except IdentityVerifierNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except IdentityVerificationError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


def register_oauth_broker() -> None:
    router = APIRouter()

    @router.get("/authorize", include_in_schema=False)
    async def authorize(
        run_id: str = Query(...),
        node_run_id: str = Query(...),
        actor_id: str = Query(...),
        target: str = Query(...),
        org_id: str | None = Query(default=None),
    ) -> RedirectResponse:
        provider = _require_provider(target)
        resolved_org_id = await _verify_actor(run_id, actor_id, org_id)
        state = sign_state(run_id, node_run_id, actor_id, resolved_org_id, target)

        logger.info("Starting OAuth authorization", run_id=run_id, target=target)
        return RedirectResponse(
            provider.authorization_url(_redirect_uri(), state), status_code=302
        )

    @router.get("/callback", include_in_schema=False)
    async def callback(
        code: str = Query(...), state: str = Query(...)
    ) -> RedirectResponse:
        try:
            payload = verify_state(state)
        except InvalidStateError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        provider = _require_provider(payload.target)
        await _verify_actor(payload.run_id, payload.actor_id, payload.org_id)

        try:
            record = await provider.exchange_code(code, _redirect_uri())
        except OAuthError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        vault_client = ocean.app.vault_client
        if vault_client is None:
            raise HTTPException(
                status_code=503,
                detail="Vault client is not configured. Set ocean.app.vault_client during integration startup.",
            )

        try:
            await vault_client.write(
                payload.org_id, payload.actor_id, payload.target, record
            )
        except VaultError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        headers = await ocean.port_client.auth.headers()
        response = await http_async_client.post(
            _resume_api_url(payload.run_id, payload.node_run_id), headers=headers
        )
        if response.status_code >= 400:
            logger.warning(
                "Failed to resume the run",
                run_id=payload.run_id,
                status_code=response.status_code,
            )

        logger.info(
            "Stored the user's token, resuming the run",
            run_id=payload.run_id,
            target=payload.target,
        )
        return RedirectResponse(_run_view_url(payload.run_id), status_code=302)

    ocean.app.fast_api_app.include_router(
        router, prefix=f"{ocean.app.route_prefix}/v1/oauth-broker"
    )
