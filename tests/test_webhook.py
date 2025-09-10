import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient

# Your FastAPI app must be exported from main.py as `app`
# e.g., in main.py: from port_ocean.context.ocean import ocean; app = ocean.app
from main import app


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OCEAN__INTEGRATION__SECRETS__GITHUB_WEBHOOK_SECRET", "topsecret")


client = TestClient(app)


def _sig(body: bytes) -> str:
    mac = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def test_webhook_rejects_missing_signature():
    resp = client.post("/webhooks/github", data=b"{}")
    assert resp.status_code in (400, 401)


def test_webhook_rejects_bad_signature():
    headers = {"X-Hub-Signature-256": "sha256=deadbeef"}
    resp = client.post("/webhooks/github", headers=headers, data=b"{}")
    assert resp.status_code == 401


def test_webhook_accepts_valid_signature_push_event():
    payload = {"zen": "Keep it logically awesome."}
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": _sig(body),
    }
    resp = client.post("/webhooks/github", headers=headers, data=body)
    assert resp.status_code in (200, 202)


def test_webhook_ignores_unhandled_event_but_ok():
    payload = {"action": "created"}
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": _sig(body),
    }
    resp = client.post("/webhooks/github", headers=headers, data=body)
    assert resp.status_code in (200, 204)