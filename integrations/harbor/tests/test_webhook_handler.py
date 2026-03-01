import hmac
import json
from types import SimpleNamespace

import pytest

from integrations.harbor.webhooks import handler as webhook_handler
from integrations.harbor.webhooks.handler import HarborWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


class FakeRequest:
    def __init__(self, headers, body):
        self.headers = headers
        self._body = body

    async def body(self):  # pragma: no cover - simple awaitable for tests
        return self._body


def runtime_stub(secret="secret"):
    settings = SimpleNamespace(
        webhook_secret=secret,
        artifact_tag_filter=[],
        artifact_digest_filter=[],
        artifact_label_filter=[],
        artifact_media_type_filter=[],
        artifact_created_since=None,
        artifact_vuln_severity_at_least=None,
        max_concurrency=2,
        max_retries=2,
        retry_jitter_seconds=0.0,
        log_level=None,
        port_org_id="port-test-org",
    )

    class _Runtime:
        def __init__(self, settings):
            self.settings = settings

        def create_client(self):  # pragma: no cover - not used in tests
            raise NotImplementedError

        def resolve_port_org_id(self):
            return getattr(self.settings, "port_org_id", None)

    return _Runtime(settings)


@pytest.fixture(autouse=True)
def patch_runtime(monkeypatch):
    monkeypatch.setattr(webhook_handler, "_get_runtime", lambda: runtime_stub())


@pytest.mark.asyncio
async def test_webhook_signature_valid(monkeypatch):
    runtime = runtime_stub()
    monkeypatch.setattr(webhook_handler, "_get_runtime", lambda: runtime)

    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "repository": {"repo_full_name": "proj/repo"},
            "resources": [{"digest": "sha256:abc", "tag": "latest"}],
        },
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(
        runtime.settings.webhook_secret.encode(), body, "sha256"
    ).hexdigest()
    headers = {
        "X-Harbor-Signature": f"sha256={signature}",
        "X-Harbor-Event": "PUSH_ARTIFACT",
    }
    request = FakeRequest(headers, body)
    event = WebhookEvent("trace", payload, headers, original_request=request)

    processor = HarborWebhookProcessor(event)
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_webhook_signature_invalid(monkeypatch):
    runtime = runtime_stub()
    monkeypatch.setattr(webhook_handler, "_get_runtime", lambda: runtime)

    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {"repository": {"repo_full_name": "proj/repo"}, "resources": []},
    }
    body = json.dumps(payload).encode()
    headers = {
        "X-Harbor-Signature": "sha256=invalid",
        "X-Harbor-Event": "PUSH_ARTIFACT",
    }
    request = FakeRequest(headers, body)
    event = WebhookEvent("trace", payload, headers, original_request=request)

    processor = HarborWebhookProcessor(event)
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_handle_event_logs_org_id(monkeypatch):
    runtime = runtime_stub()
    monkeypatch.setattr(webhook_handler, "_get_runtime", lambda: runtime)

    captured: dict[str, object] = {}

    def fake_log_webhook_event(
        event_type,
        *,
        updated,
        deleted,
        verified,
        organization_id=None,
    ):
        captured["event_type"] = event_type
        captured["organization_id"] = organization_id
        captured["updated"] = updated
        captured["deleted"] = deleted
        captured["verified"] = verified

    monkeypatch.setattr(webhook_handler, "log_webhook_event", fake_log_webhook_event)

    async def fake_fetch_artifacts(self, repository_context, resources):
        return []

    monkeypatch.setattr(
        HarborWebhookProcessor,
        "_fetch_artifacts",
        fake_fetch_artifacts,
    )

    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "repository": {"repo_full_name": "proj/repo"},
            "resources": [{"digest": "sha256:abc", "tag": "latest"}],
        },
    }
    headers = {"X-Harbor-Event": "PUSH_ARTIFACT"}
    request = FakeRequest(headers, json.dumps(payload).encode())
    event = WebhookEvent("trace", payload, headers, original_request=request)

    processor = HarborWebhookProcessor(event)
    processor._last_verification = True

    result = await processor.handle_event(payload, ResourceConfig())

    assert isinstance(result.updated_raw_results, list)
    assert captured["event_type"] == "PUSH_ARTIFACT"
    assert captured["organization_id"] == "port-test-org"
