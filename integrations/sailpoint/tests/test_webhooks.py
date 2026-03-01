import hashlib
import hmac
import json

from fastapi import FastAPI
from integrations.sailpoint.client import TOKEN_PATH, SailPointClient
from integrations.sailpoint.webhooks.router import create_router
from starlette.testclient import TestClient

from .conftest import FakeResponse, fixture_json


def sign(secret, body):
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return "sha256=" + sig


def test_webhook_identity_created_verifies_hmac_and_ingests(fake_http, cfg, ocean_ctx):
    base = f"https://{cfg.auth.tenant}.api.sailpoint.com"
    fake_http.register(
        "POST", f"{base}{TOKEN_PATH}", FakeResponse(200, fixture_json("token.json"))
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/identities/id-1",
        FakeResponse(200, fixture_json("identity_single.json")),
    )

    ocean, ingested = ocean_ctx
    client = SailPointClient(cfg)

    app = FastAPI()
    app.include_router(create_router(client, cfg, ocean), prefix="/sailpoint")

    body = json.dumps(fixture_json("webhook_identity_created.json")).encode()
    headers = {"X-SailPoint-Signature": sign(cfg.runtime.webhook_hmac_secret, body)}

    c = TestClient(app)
    r = c.post("/sailpoint/webhook", content=body, headers=headers)
    assert r.status_code == 200

    assert len(ingested["batches"]) == 1
    batch = ingested["batches"][0]
    assert batch["blueprint"] == "sailpoint_identity"
    assert batch["entities"][0]["identifier"] == "id-1"
