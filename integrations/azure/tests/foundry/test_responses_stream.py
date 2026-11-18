from azure_integration.foundry.helpers.responses_stream import (
    ResponsesSseEvent,
    format_responses_sse_log_message,
    parse_responses_sse_payload,
    response_id_from_sse_event,
    success_for_terminal_sse_event,
)


def test_parse_responses_sse_payload_invalid() -> None:
    assert parse_responses_sse_payload("not-json") is None
    assert parse_responses_sse_payload('["list"]') is None
    assert parse_responses_sse_payload("{}") is None  # type required


def test_parse_responses_sse_payload_envelope() -> None:
    event = parse_responses_sse_payload(
        '{"type":"response.created","response":{"id":"resp_1","output":[]}}'
    )
    assert event is not None
    assert event.type == "response.created"
    assert event.response == {"id": "resp_1", "output": []}


def test_format_skips_noise_events() -> None:
    assert (
        format_responses_sse_log_message(
            ResponsesSseEvent(type="response.created", response={"id": "r1"})
        )
        is None
    )
    assert (
        format_responses_sse_log_message(
            ResponsesSseEvent(type="response.output_text.delta", text="Hi")
        )
        is None
    )


def test_format_output_text_done() -> None:
    message = format_responses_sse_log_message(
        ResponsesSseEvent(
            type="response.output_text.done",
            text="Hey! How can I help you today?",
        )
    )
    assert message == "Hey! How can I help you today?"


def test_format_completed_usage() -> None:
    message = format_responses_sse_log_message(
        ResponsesSseEvent(
            type="response.completed",
            response={
                "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        )
    )
    assert (
        message == "Response completed (inputTokens=10, outputTokens=5, totalTokens=15)"
    )


def test_response_id_from_sse_created() -> None:
    assert (
        response_id_from_sse_event(
            ResponsesSseEvent(
                type="response.created",
                response={"id": "resp_xyz"},
            )
        )
        == "resp_xyz"
    )


def test_success_for_terminal_sse_event() -> None:
    assert success_for_terminal_sse_event("response.completed") is True
    assert success_for_terminal_sse_event("response.failed") is False
    assert success_for_terminal_sse_event("response.created") is None
