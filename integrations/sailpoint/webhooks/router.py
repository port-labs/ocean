from fastapi import APIRouter, HTTPException, Request

from ..client import SailPointClient
from ..mapping import map_identity


def create_router(client: SailPointClient, cfg, ocean):
    r = APIRouter()

    @r.post("/webhook")
    async def webhook(req: Request):
        body = await req.body()
        sig = req.headers.get("X-SailPoint-Signature")
        if cfg.runtime.webhook_hmac_secret:
            from .hmac import verify_hmac

            if not sig or not verify_hmac(cfg.runtime.webhook_hmac_secret, body, sig):
                raise HTTPException(status_code=401, detail="Invalid signature")

        data = await req.json()
        if data.get("eventType") in ("IDENTITY_CREATED", "IDENTITY_UPDATED"):
            ident_id = data["resource"]["id"]
            sp = await client.get(f"/v2025/identities/{ident_id}")
            entity = map_identity(sp)
            await ocean.port_client.ingest_entities("sailpoint_identity", [entity])
        # Extend for Accounts/Entitlements/Requests/Campaigns…
        return {"ok": True}

    return r
