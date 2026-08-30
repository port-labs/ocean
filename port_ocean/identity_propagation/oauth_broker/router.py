from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.identity_propagation import (
    IdentityVerifierNotAvailableError,
    IdentityVerificationError,
    OAuthError,
    OAuthProviderNotConfiguredError,
    VaultError,
)
from port_ocean.identity_propagation.oauth_broker.providers import require_provider
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


def _run_view_url(org_id: str, run_id: str) -> str:
    configured_app_url = ocean.config.port.app_url
    if configured_app_url is not None:
        app_url = str(configured_app_url).rstrip("/")
    else:
        # Fallback: guess the app URL from the API URL (api.getport.io -> app.getport.io).
        # Set OCEAN__PORT__APP_URL to skip this guess — it breaks if the app domain doesn't
        # follow that exact convention (e.g. api.stg-01.getport.io vs app.stg-01.port.io).
        api_url = ocean.port_client.api_url.rstrip("/")
        app_url = api_url.replace("api.", "app.").removesuffix("/v1")
    return f"{app_url}/{org_id}/organization/workflow-run?runId={run_id}"


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
        run_id: str = Query(..., alias="runId"),
        node_run_id: str = Query(..., alias="nodeRunId"),
        actor_id: str = Query(..., alias="actorId"),
        org_id: str | None = Query(default=None, alias="orgId"),
    ) -> RedirectResponse:
        try:
            provider = require_provider()
        except OAuthProviderNotConfiguredError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        resolved_org_id = await _verify_actor(run_id, actor_id, org_id)
        state = sign_state(run_id, node_run_id, actor_id, resolved_org_id)

        logger.info(
            "Starting OAuth authorization", run_id=run_id, target=provider.target
        )
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

        try:
            provider = require_provider()
        except OAuthProviderNotConfiguredError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
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

        # Keyed by this process's own identity (there is no caller-supplied target anymore) —
        # matches what token_exchanger.py reads on the other side.
        try:
            await vault_client.write(
                payload.org_id, payload.actor_id, provider.target, record
            )
        except VaultError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        # x-port-reserved-usage marks this as a Port-operated caller (mirrors verifier.py and
        # the claim-pending mixins) — workflow-service's resume endpoint requires it from machine
        # callers instead of an installationId/clientId ownership lookup.
        headers = {
            **await ocean.port_client.auth.headers(),
            "x-port-reserved-usage": "true",
        }
        response = await http_async_client.post(
            _resume_api_url(payload.run_id, payload.node_run_id), headers=headers
        )
        if response.status_code >= 400:
            logger.warning(
                f"Failed to resume the run: status_code={response.status_code} "
                f"response_body={response.text!r} run_id={payload.run_id} "
                f"node_run_id={payload.node_run_id}"
            )

        logger.info(
            "Stored the user's token, resuming the run",
            run_id=payload.run_id,
            target=provider.target,
        )
        return RedirectResponse(
            _run_view_url(payload.org_id, payload.run_id), status_code=302
        )

    ocean.app.fast_api_app.include_router(
        router, prefix=f"{ocean.app.route_prefix}/v1/oauth-broker"
    )
