from azure_integration.foundry.helpers.responses_stream import (
    TERMINAL_SSE_TYPES,
    ResponsesSseEvent,
    format_responses_sse_log_message,
    parse_responses_sse_payload,
    response_id_from_sse_event,
)


def test_parse_and_format() -> None:
    assert parse_responses_sse_payload("not-json") is None
    assert parse_responses_sse_payload("{}") is None
    event = parse_responses_sse_payload(
        '{"type":"response.created","response":{"id":"resp_1"}}'
    )
    assert event is not None
    assert response_id_from_sse_event(event) == "resp_1"
    assert (
        format_responses_sse_log_message(
            ResponsesSseEvent(type="response.output_text.delta", text="Hi")
        )
        is None
    )
    assert (
        format_responses_sse_log_message(
            ResponsesSseEvent(type="response.output_text.done", text="Hey!")
        )
        == "Hey!"
    )
    assert TERMINAL_SSE_TYPES.get("response.completed") is True
    assert TERMINAL_SSE_TYPES.get("response.failed") is False
    assert TERMINAL_SSE_TYPES.get("response.created") is None
