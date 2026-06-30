from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types.beta.sessions.beta_managed_agents_agent_message_event import (
    BetaManagedAgentsAgentMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_agent_tool_use_event import (
    BetaManagedAgentsAgentToolUseEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_billing_error import (
    BetaManagedAgentsBillingError,
)
from anthropic.types.beta.sessions.beta_managed_agents_model_rate_limited_error import (
    BetaManagedAgentsModelRateLimitedError,
)
from anthropic.types.beta.sessions.beta_managed_agents_retry_status_exhausted import (
    BetaManagedAgentsRetryStatusExhausted,
)
from anthropic.types.beta.sessions.beta_managed_agents_retry_status_retrying import (
    BetaManagedAgentsRetryStatusRetrying,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_end_turn import (
    BetaManagedAgentsSessionEndTurn,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_error_event import (
    BetaManagedAgentsSessionErrorEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_event import (
    BetaManagedAgentsSessionEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_retries_exhausted import (
    BetaManagedAgentsSessionRetriesExhausted,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
    BetaManagedAgentsSessionStatusIdleEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.models import (
    WorkflowNodeRun,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)

from actions.utils import build_external_id
from webhook_processors.session_webhook_processor import SessionWebhookProcessor
from webhook_processors.trigger_agent_webhook_processor import (
    TriggerAgentWebhookProcessor,
)
from webhook_processors.vault_webhook_processor import VaultWebhookProcessor


def _event(data: dict[str, Any]) -> WebhookEvent:
    return WebhookEvent(trace_id="trace", payload={"data": data}, headers={})


# --- session ---


@pytest.mark.asyncio
async def test_session_should_process_and_kinds() -> None:
    processor = SessionWebhookProcessor(_event({"type": "session.idled", "id": "s1"}))
    assert await processor.should_process_event(processor.event) is True
    assert await processor.get_matching_kinds(processor.event) == ["session"]


@pytest.mark.asyncio
async def test_session_validate_payload() -> None:
    processor = SessionWebhookProcessor(_event({"type": "session.idled", "id": "s1"}))
    assert await processor.validate_payload({"data": {"type": "t", "id": "i"}}) is True
    assert await processor.validate_payload({"data": {}}) is False


@pytest.mark.asyncio
async def test_session_delete_event_returns_delete() -> None:
    payload = {"data": {"type": "session.deleted", "id": "s1"}}
    processor = SessionWebhookProcessor(_event(payload["data"]))
    results = await processor.handle_event(payload, None)
    assert results.deleted_raw_results == [{"id": "s1"}]
    assert results.updated_raw_results == []


@pytest.mark.asyncio
async def test_session_upsert_event_fetches_resource() -> None:
    payload = {"data": {"type": "session.running", "id": "s1"}}
    processor = SessionWebhookProcessor(_event(payload["data"]))
    client = MagicMock()
    client.get_session = AsyncMock(return_value={"id": "s1", "status": "running"})
    with patch(
        "webhook_processors.session_webhook_processor.create_anthropic_client",
        return_value=client,
    ):
        results = await processor.handle_event(payload, None)
    assert results.updated_raw_results == [{"id": "s1", "status": "running"}]
    client.get_session.assert_awaited_once_with("s1")


# --- vault ---


@pytest.mark.asyncio
async def test_vault_should_not_process_credential_events() -> None:
    processor = VaultWebhookProcessor(
        _event({"type": "vault_credential.created", "id": "c1", "vault_id": "v1"})
    )
    assert await processor.should_process_event(processor.event) is False


@pytest.mark.asyncio
async def test_vault_delete_event_returns_delete() -> None:
    payload = {"data": {"type": "vault.deleted", "id": "v1"}}
    processor = VaultWebhookProcessor(_event(payload["data"]))
    results = await processor.handle_event(payload, None)
    assert results.deleted_raw_results == [{"id": "v1"}]


# --- trigger agent (action) ---


@pytest.mark.asyncio
async def test_trigger_processor_type_is_action() -> None:
    processor = TriggerAgentWebhookProcessor(
        _event({"type": "session.idled", "id": "s1"})
    )
    assert processor.get_processor_type() == WebhookProcessorType.ACTION
    assert await processor.get_matching_kinds(processor.event) == []


@pytest.mark.asyncio
async def test_trigger_should_process_only_terminal_events() -> None:
    idled = TriggerAgentWebhookProcessor(_event({"type": "session.idled", "id": "s1"}))
    running = TriggerAgentWebhookProcessor(
        _event({"type": "session.running", "id": "s1"})
    )
    assert await idled.should_process_event(idled.event) is True
    assert await running.should_process_event(running.event) is False


def _wf_node_run(report_status: bool = True) -> MagicMock:
    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {"sessionId": "s1", "userMessageEventId": _ANCHOR_ID}
    run.execution_properties = {"reportSessionStatus": report_status}
    return run


_TS = datetime(2026, 6, 15, 8, 58, tzinfo=timezone.utc)
_WH_TS = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
_ANCHOR_ID = "msg_anchor"


def _webhook_payload(
    session_id: str = "s1",
    event_type: str = "session.idled",
    created_at: datetime = _WH_TS,
) -> dict[str, Any]:
    return {
        "id": "wh_1",
        "type": "event",
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "data": {
            "type": event_type,
            "id": session_id,
            "organization_id": "org_1",
            "workspace_id": "ws_1",
        },
    }


def _user_message(
    text: str,
    *,
    event_id: str = _ANCHOR_ID,
    processed_at: datetime = _TS,
) -> BetaManagedAgentsUserMessageEvent:
    return BetaManagedAgentsUserMessageEvent(
        id=event_id,
        type="user.message",
        processed_at=processed_at,
        content=[BetaManagedAgentsTextBlock(type="text", text=text)],
    )


def _agent_message(text: str) -> BetaManagedAgentsAgentMessageEvent:
    return BetaManagedAgentsAgentMessageEvent(
        id="e",
        type="agent.message",
        processed_at=_TS,
        content=[BetaManagedAgentsTextBlock(type="text", text=text)],
    )


def _tool_use(name: str) -> BetaManagedAgentsAgentToolUseEvent:
    return BetaManagedAgentsAgentToolUseEvent(
        id="e", type="agent.tool_use", name=name, input={}, processed_at=_TS
    )


def _patch_session_events(
    anchor: BetaManagedAgentsUserMessageEvent,
    interaction_batches: list[list[BetaManagedAgentsSessionEvent]],
    *,
    prior_idle: BetaManagedAgentsSessionStatusIdleEvent | None = None,
    agent_message_batches: list[list[BetaManagedAgentsSessionEvent]] | None = None,
) -> Any:
    async def _gen(_session_id: str, **kwargs: Any) -> Any:
        if kwargs.get("types") == ["user.message"] and kwargs.get("order") == "desc":
            yield [anchor]
            return
        if (
            kwargs.get("types") == ["session.status_idle"]
            and kwargs.get("order") == "desc"
            and kwargs.get("created_at_lt") is not None
        ):
            if prior_idle is not None:
                yield [prior_idle]
            return
        if kwargs.get("types") == ["session.error", "session.status_idle"]:
            if prior_idle is not None:
                if kwargs.get("created_at_gt") == prior_idle.processed_at:
                    for batch in interaction_batches:
                        yield batch
            elif (
                kwargs.get("created_at_gt") is None
                and kwargs.get("created_at_lte") is not None
            ):
                for batch in interaction_batches:
                    yield batch
            return
        if kwargs.get("types") == ["agent.message"]:
            if prior_idle is not None:
                if kwargs.get("created_at_gt") == prior_idle.processed_at:
                    for batch in agent_message_batches or []:
                        yield batch
            elif kwargs.get("created_at_gte") is not None:
                for batch in agent_message_batches or []:
                    yield batch
            elif (
                kwargs.get("created_at_gt") is None
                and kwargs.get("created_at_lte") is not None
            ):
                for batch in agent_message_batches or []:
                    yield batch
            return

    client = MagicMock()
    client.get_session_events = _gen
    return patch(
        "webhook_processors.trigger_agent_webhook_processor.create_anthropic_client",
        return_value=client,
    )


def _billing_error() -> BetaManagedAgentsSessionErrorEvent:
    return BetaManagedAgentsSessionErrorEvent(
        id="e",
        type="session.error",
        processed_at=_TS,
        error=BetaManagedAgentsBillingError(
            type="billing_error",
            message="Your credit balance is too low to access the Anthropic API.",
            retry_status=BetaManagedAgentsRetryStatusExhausted(type="exhausted"),
        ),
    )


def _rate_limited_retrying() -> BetaManagedAgentsSessionErrorEvent:
    return BetaManagedAgentsSessionErrorEvent(
        id="e",
        type="session.error",
        processed_at=_TS,
        error=BetaManagedAgentsModelRateLimitedError(
            type="model_rate_limited_error",
            message="Rate limited",
            retry_status=BetaManagedAgentsRetryStatusRetrying(type="retrying"),
        ),
    )


def _idle(stop_reason: Any) -> BetaManagedAgentsSessionStatusIdleEvent:
    return BetaManagedAgentsSessionStatusIdleEvent(
        id="e", type="session.status_idle", processed_at=_TS, stop_reason=stop_reason
    )


@pytest.mark.asyncio
async def test_trigger_reports_success_without_error_logs() -> None:
    anchor = _user_message("do the thing")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    batch: list[BetaManagedAgentsSessionEvent] = [
        _idle(BetaManagedAgentsSessionEndTurn(type="end_turn")),
    ]

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(anchor, [batch]),
    ):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.find_run_by_external_id.assert_awaited_once_with(
        build_external_id("s1", _ANCHOR_ID)
    )
    mock_ocean.port_client.post_wf_node_run_logs.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True
    assert mock_ocean.port_client.report_run_completed.call_args.kwargs == {}


@pytest.mark.asyncio
async def test_trigger_reports_response_on_success() -> None:
    anchor = _user_message("do the thing")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    batch: list[BetaManagedAgentsSessionEvent] = [
        _idle(BetaManagedAgentsSessionEndTurn(type="end_turn")),
    ]

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(
            anchor,
            [batch],
            agent_message_batches=[[_agent_message("All done.")]],
        ),
    ):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once_with(
        "run_1",
        {
            "status": WorkflowNodeRunStatus.COMPLETED,
            "result": WorkflowNodeRunResult.SUCCESS,
            "output": {
                "sessionId": "s1",
                "userMessageEventId": _ANCHOR_ID,
                "response": "All done.",
            },
        },
    )


@pytest.mark.asyncio
async def test_trigger_reports_success_when_session_error_has_end_turn() -> None:
    """Exhausted session.error with end_turn idle is logged but still succeeds."""
    anchor = _user_message("hello")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    batch: list[BetaManagedAgentsSessionEvent] = [
        _billing_error(),
        _idle(BetaManagedAgentsSessionEndTurn(type="end_turn")),
    ]

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(
            anchor,
            [batch],
            agent_message_batches=[[_agent_message("Recovered.")]],
        ),
    ):
        await processor.handle_event(payload, None)

    logs = mock_ocean.port_client.post_wf_node_run_logs.call_args.args[1]
    assert [log.level for log in logs] == ["ERROR"]
    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once_with(
        "run_1",
        {
            "status": WorkflowNodeRunStatus.COMPLETED,
            "result": WorkflowNodeRunResult.SUCCESS,
            "output": {
                "sessionId": "s1",
                "userMessageEventId": _ANCHOR_ID,
                "response": "Recovered.",
            },
        },
    )


@pytest.mark.asyncio
async def test_trigger_reports_failure_when_transcript_has_error() -> None:
    anchor = _user_message("Just return ok!")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    batch: list[BetaManagedAgentsSessionEvent] = [
        _billing_error(),
        _idle(BetaManagedAgentsSessionRetriesExhausted(type="retries_exhausted")),
    ]

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(anchor, [batch]),
    ):
        await processor.handle_event(payload, None)

    logs = mock_ocean.port_client.post_wf_node_run_logs.call_args.args[1]
    assert [log.message for log in logs] == [
        "Session error (billing_error): Your credit balance is too low "
        "to access the Anthropic API.",
    ]
    assert [log.level for log in logs] == ["ERROR"]
    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once_with(
        "run_1",
        {
            "status": WorkflowNodeRunStatus.COMPLETED,
            "result": WorkflowNodeRunResult.FAILED,
            "output": {
                "sessionId": "s1",
                "userMessageEventId": _ANCHOR_ID,
                "error": "Session error (billing_error): Your credit balance is too low "
                "to access the Anthropic API.",
            },
        },
    )


@pytest.mark.asyncio
async def test_trigger_reports_success_when_transient_error_recovered() -> None:
    anchor = _user_message("hello")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    batch: list[BetaManagedAgentsSessionEvent] = [
        _rate_limited_retrying(),
        _idle(BetaManagedAgentsSessionEndTurn(type="end_turn")),
    ]

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(anchor, [batch]),
    ):
        await processor.handle_event(payload, None)

    logs = mock_ocean.port_client.post_wf_node_run_logs.call_args.args[1]
    assert [log.message for log in logs] == [
        "Session error (model_rate_limited_error): Rate limited",
    ]
    assert [log.level for log in logs] == ["WARN"]
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True
    assert mock_ocean.port_client.report_run_completed.call_args.kwargs == {}
    anchor = _user_message("try again")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    failed_batch: list[BetaManagedAgentsSessionEvent] = [
        _idle(BetaManagedAgentsSessionRetriesExhausted(type="retries_exhausted")),
    ]

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(anchor, [failed_batch]),
    ):
        await processor.handle_event(payload, None)

    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is False
    assert mock_ocean.port_client.report_run_completed.call_args.kwargs == {}
    anchor = _user_message("go")
    payload = _webhook_payload(event_type="session.status_terminated")
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(anchor, []),
    ):
        await processor.handle_event(payload, None)

    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is False


@pytest.mark.asyncio
async def test_trigger_completes_run_when_error_inspection_fails() -> None:
    anchor = _user_message("go")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    client = MagicMock()

    async def _failing_events(_session_id: str, **kwargs: Any) -> Any:
        if kwargs.get("types") == ["user.message"]:
            yield [anchor]
            return
        if kwargs.get("types") == ["session.status_idle"]:
            return
        raise RuntimeError("api down")

    client.get_session_events = _failing_events

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        patch(
            "webhook_processors.trigger_agent_webhook_processor.create_anthropic_client",
            return_value=client,
        ),
    ):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.post_wf_node_run_logs.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True


@pytest.mark.asyncio
async def test_trigger_skips_when_report_disabled() -> None:
    anchor = _user_message("go")
    payload = _webhook_payload()
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run(report_status=False)
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        _patch_session_events(anchor, []),
    ):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_delayed_webhook_anchors_prior_run() -> None:
    """A newer user message after webhook time must not steal correlation."""
    anchor_a = _user_message("run A", event_id="msg_a", processed_at=_TS)
    _user_message(
        "run B",
        event_id="msg_b",
        processed_at=datetime(2026, 6, 15, 9, 5, tzinfo=timezone.utc),
    )
    payload = _webhook_payload(created_at=_WH_TS)
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    batch_a: list[BetaManagedAgentsSessionEvent] = [
        _idle(BetaManagedAgentsSessionEndTurn(type="end_turn")),
    ]

    async def _gen(_session_id: str, **kwargs: Any) -> Any:
        if kwargs.get("types") == ["user.message"] and kwargs.get("order") == "desc":
            yield [anchor_a]
            return
        if (
            kwargs.get("types") == ["session.status_idle"]
            and kwargs.get("order") == "desc"
        ):
            return
        if (
            kwargs.get("types") == ["session.error", "session.status_idle"]
            and kwargs.get("created_at_gt") is None
            and kwargs.get("created_at_lte") is not None
        ):
            yield batch_a

    client = MagicMock()
    client.get_session_events = _gen

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        patch(
            "webhook_processors.trigger_agent_webhook_processor.create_anthropic_client",
            return_value=client,
        ),
    ):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.find_run_by_external_id.assert_awaited_once_with(
        build_external_id("s1", "msg_a")
    )
    mock_ocean.port_client.post_wf_node_run_logs.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_continuation_scopes_errors_to_current_interaction() -> None:
    """Errors from a prior turn must not appear in a continuation run's logs."""
    turn_one_idle_ts = datetime(2026, 6, 15, 16, 50, 40, tzinfo=timezone.utc)
    turn_two_anchor = _user_message(
        "Try again!",
        event_id="msg_turn_2",
        processed_at=datetime(2026, 6, 15, 16, 50, 41, tzinfo=timezone.utc),
    )
    payload = _webhook_payload(
        created_at=datetime(2026, 6, 15, 16, 50, 43, tzinfo=timezone.utc)
    )
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    turn_one_idle = BetaManagedAgentsSessionStatusIdleEvent(
        id="idle_turn_1",
        type="session.status_idle",
        processed_at=turn_one_idle_ts,
        stop_reason=BetaManagedAgentsSessionEndTurn(type="end_turn"),
    )
    turn_two_error = BetaManagedAgentsSessionErrorEvent(
        id="err_turn_2",
        type="session.error",
        processed_at=datetime(2026, 6, 15, 16, 50, 41, 753573, tzinfo=timezone.utc),
        error=BetaManagedAgentsBillingError(
            type="billing_error",
            message="Your credit balance is too low to access the Anthropic API.",
            retry_status=BetaManagedAgentsRetryStatusExhausted(type="exhausted"),
        ),
    )
    interaction_batch: list[BetaManagedAgentsSessionEvent] = [
        turn_two_error,
        _idle(BetaManagedAgentsSessionRetriesExhausted(type="retries_exhausted")),
    ]

    async def _gen(_session_id: str, **kwargs: Any) -> Any:
        if kwargs.get("types") == ["user.message"] and kwargs.get("order") == "desc":
            yield [turn_two_anchor]
            return
        if (
            kwargs.get("types") == ["session.status_idle"]
            and kwargs.get("order") == "desc"
            and kwargs.get("created_at_lt") is not None
        ):
            yield [turn_one_idle]
            return
        if (
            kwargs.get("types") == ["session.error", "session.status_idle"]
            and kwargs.get("created_at_gt") == turn_one_idle_ts
        ):
            yield interaction_batch

    client = MagicMock()
    client.get_session_events = _gen

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        patch(
            "webhook_processors.trigger_agent_webhook_processor.create_anthropic_client",
            return_value=client,
        ),
    ):
        await processor.handle_event(payload, None)

    mock_ocean.port_client.find_run_by_external_id.assert_awaited_once_with(
        build_external_id("s1", "msg_turn_2")
    )
    logs = mock_ocean.port_client.post_wf_node_run_logs.call_args.args[1]
    assert len(logs) == 1
    assert "billing_error" in logs[0].message
    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_message_after_idle_still_scopes_via_prior_idle() -> None:
    """When user.message appears after idle in the stream, prior idle still scopes errors."""
    wh_ts = datetime(2026, 6, 15, 16, 50, 43, tzinfo=timezone.utc)
    prior_idle_ts = datetime(2026, 6, 15, 16, 50, 40, tzinfo=timezone.utc)
    msg_ts = datetime(2026, 6, 15, 16, 50, 41, tzinfo=timezone.utc)
    err_ts = datetime(2026, 6, 15, 16, 50, 41, 753573, tzinfo=timezone.utc)
    idle_ts = datetime(2026, 6, 15, 16, 50, 42, 169848, tzinfo=timezone.utc)

    anchor = BetaManagedAgentsUserMessageEvent(
        id="msg_try_again",
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="Try again!")],
        processed_at=msg_ts,
    )
    payload = _webhook_payload(created_at=wh_ts)
    processor = TriggerAgentWebhookProcessor(_event(payload["data"]))

    run = _wf_node_run()
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_wf_node_run_logs = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    prior_idle = BetaManagedAgentsSessionStatusIdleEvent(
        id="idle_turn_1",
        type="session.status_idle",
        processed_at=prior_idle_ts,
        stop_reason=BetaManagedAgentsSessionEndTurn(type="end_turn"),
    )
    billing = BetaManagedAgentsSessionErrorEvent(
        id="err_2",
        type="session.error",
        processed_at=err_ts,
        error=BetaManagedAgentsBillingError(
            type="billing_error",
            message="Your credit balance is too low to access the Anthropic API.",
            retry_status=BetaManagedAgentsRetryStatusExhausted(type="exhausted"),
        ),
    )
    idle = BetaManagedAgentsSessionStatusIdleEvent(
        id="idle_2",
        type="session.status_idle",
        processed_at=idle_ts,
        stop_reason=BetaManagedAgentsSessionRetriesExhausted(type="retries_exhausted"),
    )

    async def _gen(_session_id: str, **kwargs: Any) -> Any:
        if kwargs.get("types") == ["user.message"] and kwargs.get("order") == "desc":
            yield [anchor]
            return
        if (
            kwargs.get("types") == ["session.status_idle"]
            and kwargs.get("order") == "desc"
            and kwargs.get("created_at_lt") is not None
        ):
            yield [prior_idle]
            return
        if (
            kwargs.get("types") == ["session.error", "session.status_idle"]
            and kwargs.get("created_at_gt") == prior_idle_ts
        ):
            yield [billing, idle]

    client = MagicMock()
    client.get_session_events = _gen

    with (
        patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean),
        patch(
            "webhook_processors.trigger_agent_webhook_processor.create_anthropic_client",
            return_value=client,
        ),
    ):
        await processor.handle_event(payload, None)

    logs = mock_ocean.port_client.post_wf_node_run_logs.call_args.args[1]
    assert len(logs) == 1
    assert "billing_error" in logs[0].message
    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once()
