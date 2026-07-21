from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import WorkflowNodeRun

import core.webhook_signing as webhook_signing
from core.webhook_signing import derive_webhook_secret
from integration import ObjectKind
from webhook_processors.cursor_agent_webhook_processor import (
    CursorAgentWebhookProcessor,
)


@pytest.fixture(autouse=True)
def _reset_org_id_cache() -> None:
    webhook_signing._org_id_cache = None


def _build_processor() -> CursorAgentWebhookProcessor:
    event = MagicMock()
    return CursorAgentWebhookProcessor(event)


@asynccontextmanager
async def _noop_event_context(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield


def _mock_cursor_client(*, runs: list[dict[str, object]]) -> MagicMock:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    run_id = runs[0]["id"] if runs else "cursor-run-1"

    async def _send_api_request(
        method: str,
        path: str,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if path.endswith("/usage"):
            return {
                "runs": [
                    {
                        "id": run_id,
                        "usage": {
                            "inputTokens": 10,
                            "outputTokens": 20,
                            "cacheReadTokens": 0,
                            "cacheWriteTokens": 0,
                            "totalTokens": 30,
                        },
                    }
                ]
            }
        if path.endswith(f"/runs/{run_id}"):
            return {
                "id": run_id,
                "status": "FINISHED",
                "agentId": "bc-1",
                "updatedAt": "2025-06-01T12:05:00Z",
            }
        if path.endswith("/runs"):
            return {"items": runs}
        return {}

    client_mock.send_api_request = AsyncMock(side_effect=_send_api_request)
    client_mock.page_size = 20
    return client_mock


def _patch_handle_event(mock_ocean: MagicMock, client_mock: MagicMock) -> ExitStack:
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    stack = ExitStack()
    stack.enter_context(
        patch("webhook_processors.cursor_agent_webhook_processor.ocean", mock_ocean)
    )
    stack.enter_context(patch("webhook_processors.utils.ocean", mock_ocean))
    stack.enter_context(patch("core.catalog.ocean", mock_ocean))
    stack.enter_context(patch("core.catalog.event_context", _noop_event_context))
    stack.enter_context(
        patch(
            "webhook_processors.utils.create_cursor_agents_client",
            return_value=client_mock,
        )
    )
    stack.enter_context(
        patch(
            "webhook_processors.cursor_agent_webhook_processor.create_cursor_agents_client",
            return_value=client_mock,
        )
    )
    return stack


@pytest.mark.asyncio
async def test_should_process_event_true_for_terminal_statuses() -> None:
    processor = _build_processor()
    event = MagicMock(payload={"status": "FINISHED"})
    assert await processor.should_process_event(event) is True

    event = MagicMock(payload={"status": "ERROR"})
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_false_for_non_terminal_statuses() -> None:
    processor = _build_processor()
    for status in ("CREATING", "RUNNING", "STOPPED"):
        event = MagicMock(payload={"status": status})
        assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_validate_payload_requires_id_and_status() -> None:
    processor = _build_processor()
    assert (
        await processor.validate_payload({"id": "bc-1", "status": "FINISHED"}) is True
    )
    assert await processor.validate_payload({"id": "bc-1"}) is False
    assert await processor.validate_payload({"status": "FINISHED"}) is False


@pytest.mark.asyncio
async def test_handle_event_completes_create_run_via_agent_id_fallback() -> None:
    processor = _build_processor()

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {"agentId": "bc-1"}

    mock_ocean = MagicMock()

    async def _find_external_id(external_id: str) -> WorkflowNodeRun | None:
        if external_id == "bc-1":
            return run
        return None

    mock_ocean.port_client.find_run_by_external_id = AsyncMock(
        side_effect=_find_external_id
    )
    mock_ocean.port_client.is_run_in_progress.return_value = True
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.register_raw = AsyncMock()

    client_mock = _mock_cursor_client(
        runs=[{"id": "cursor-run-1", "createdAt": "2025-06-01T11:00:00Z"}]
    )
    payload = {
        "id": "bc-1",
        "status": "FINISHED",
        "summary": "Added README",
        "target": {"branchName": "cursor/add-readme"},
        "timestamp": "2025-06-01T12:00:00Z",
    }

    with _patch_handle_event(mock_ocean, client_mock):
        result = await processor.handle_event(payload, None)

    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Added README"
    )
    assert run.output["status"] == "FINISHED"
    assert run.output["runId"] == "cursor-run-1"
    assert mock_ocean.register_raw.await_count == 2
    mock_ocean.register_raw.assert_any_await(
        ObjectKind.AGENT,
        [
            {
                "id": "bc-1",
                "status": "ACTIVE",
                "summary": "Added README",
                "target": {"branchName": "cursor/add-readme"},
                "timestamp": "2025-06-01T12:00:00Z",
                "url": "https://cursor.com/agents/bc-1",
            }
        ],
    )
    mock_ocean.register_raw.assert_any_await(
        ObjectKind.RUN,
        [
            {
                "id": "cursor-run-1",
                "status": "FINISHED",
                "agentId": "bc-1",
                "updatedAt": "2025-06-01T12:05:00Z",
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 20,
                    "cacheReadTokens": 0,
                    "cacheWriteTokens": 0,
                    "totalTokens": 30,
                },
            }
        ],
    )
    assert result.updated_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_completes_follow_up_via_cursor_run_id() -> None:
    processor = _build_processor()

    follow_up_run = MagicMock(spec=WorkflowNodeRun)
    follow_up_run.id = "follow_up_run"
    follow_up_run.output = {"agentId": "bc-1", "runId": "cursor-run-2"}

    mock_ocean = MagicMock()

    async def _find_external_id(external_id: str) -> WorkflowNodeRun | None:
        if external_id == "cursor-run-2":
            return follow_up_run
        return None

    mock_ocean.port_client.find_run_by_external_id = AsyncMock(
        side_effect=_find_external_id
    )
    mock_ocean.port_client.is_run_in_progress.return_value = True
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.register_raw = AsyncMock()

    client_mock = _mock_cursor_client(
        runs=[{"id": "cursor-run-2", "createdAt": "2025-06-01T11:30:00Z"}]
    )
    payload = {
        "id": "bc-1",
        "status": "FINISHED",
        "summary": "Done",
        "timestamp": "2025-06-01T12:00:00Z",
    }

    with _patch_handle_event(mock_ocean, client_mock):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        follow_up_run, True, "Done"
    )
    assert follow_up_run.output["runId"] == "cursor-run-2"


@pytest.mark.asyncio
async def test_handle_event_reports_failure_on_error_status() -> None:
    processor = _build_processor()

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {"agentId": "bc-1"}

    mock_ocean = MagicMock()

    async def _find_external_id(external_id: str) -> WorkflowNodeRun | None:
        if external_id == "bc-1":
            return run
        return None

    mock_ocean.port_client.find_run_by_external_id = AsyncMock(
        side_effect=_find_external_id
    )
    mock_ocean.port_client.is_run_in_progress.return_value = True
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.register_raw = AsyncMock()

    client_mock = _mock_cursor_client(
        runs=[{"id": "cursor-run-1", "createdAt": "2025-06-01T11:00:00Z"}]
    )
    payload = {
        "id": "bc-1",
        "status": "ERROR",
        "timestamp": "2025-06-01T12:00:00Z",
    }

    with _patch_handle_event(mock_ocean, client_mock):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is False


@pytest.mark.asyncio
async def test_handle_event_upserts_catalog_when_no_run_tracked() -> None:
    processor = _build_processor()

    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=None)
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.register_raw = AsyncMock()

    client_mock = _mock_cursor_client(
        runs=[{"id": "cursor-run-1", "createdAt": "2025-06-01T11:00:00Z"}]
    )
    payload = {
        "id": "bc-1",
        "status": "FINISHED",
        "summary": "Done",
        "timestamp": "2025-06-01T12:00:00Z",
    }

    with _patch_handle_event(mock_ocean, client_mock):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    assert mock_ocean.register_raw.await_count == 2
    mock_ocean.register_raw.assert_any_await(
        ObjectKind.AGENT,
        [
            {
                "id": "bc-1",
                "status": "ACTIVE",
                "summary": "Done",
                "timestamp": "2025-06-01T12:00:00Z",
            }
        ],
    )
    mock_ocean.register_raw.assert_any_await(
        ObjectKind.RUN,
        [
            {
                "id": "cursor-run-1",
                "status": "FINISHED",
                "agentId": "bc-1",
                "updatedAt": "2025-06-01T12:05:00Z",
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 20,
                    "cacheReadTokens": 0,
                    "cacheWriteTokens": 0,
                    "totalTokens": 30,
                },
            }
        ],
    )


def _build_request(*, run_id: str | None, body: bytes) -> MagicMock:
    request = MagicMock()
    request.path_params = {"run_id": run_id} if run_id is not None else {}
    request.body = AsyncMock(return_value=body)
    return request


def _sign(secret: str, raw_body: str) -> str:
    return (
        "sha256="
        + hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    )


@pytest.mark.asyncio
async def test_authenticate_accepts_valid_signature_derived_from_run_id() -> None:
    processor = _build_processor()
    raw_body = '{"id":"bc-1","status":"FINISHED"}'

    mock_ocean = MagicMock()
    mock_ocean.config.port.client_secret = "test-port-client-secret"
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="test-org-id")
    with patch("core.webhook_signing.ocean", mock_ocean):
        secret = await derive_webhook_secret("run_1")
        request = _build_request(run_id="run_1", body=raw_body.encode())
        processor.event._original_request = request

        headers = {"X-Webhook-Signature": _sign(secret, raw_body)}
        assert await processor.authenticate({}, headers) is True


@pytest.mark.asyncio
async def test_authenticate_rejects_signature_for_wrong_run_id() -> None:
    processor = _build_processor()
    raw_body = '{"id":"bc-1","status":"FINISHED"}'

    mock_ocean = MagicMock()
    mock_ocean.config.port.client_secret = "test-port-client-secret"
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="test-org-id")
    with patch("core.webhook_signing.ocean", mock_ocean):
        secret = await derive_webhook_secret("run_1")
        request = _build_request(run_id="run_2", body=raw_body.encode())
        processor.event._original_request = request

        headers = {"X-Webhook-Signature": _sign(secret, raw_body)}
        assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_run_id() -> None:
    processor = _build_processor()
    request = _build_request(run_id=None, body=b"{}")
    processor.event._original_request = request

    assert (
        await processor.authenticate({}, {"X-Webhook-Signature": "sha256=deadbeef"})
        is False
    )


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_signature_header() -> None:
    processor = _build_processor()
    request = _build_request(run_id="run_1", body=b"{}")
    processor.event._original_request = request

    assert await processor.authenticate({}, {}) is False


def test_get_processor_type_is_action() -> None:
    from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
        WebhookProcessorType,
    )

    assert (
        CursorAgentWebhookProcessor.get_processor_type() == WebhookProcessorType.ACTION
    )
