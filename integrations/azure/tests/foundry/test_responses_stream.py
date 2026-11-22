from azure_integration.foundry.models.responses import (
    TERMINAL_EVENTS,
    ResponsesSseEvent,
)


def test_parse_and_format() -> None:
    assert ResponsesSseEvent.parse_payload("not-json") is None
    assert ResponsesSseEvent.parse_payload("{}") is None
    event = ResponsesSseEvent.parse_payload(
        '{"type":"response.created","response":{"id":"resp_1"}}'
    )
    assert event is not None
    assert event.response_id == "resp_1"
    assert (
        ResponsesSseEvent(type="response.output_text.delta", text="Hi").log_message()
        is None
    )
    assert (
        ResponsesSseEvent(type="response.output_text.done", text="Hey!").log_message()
        == "Hey!"
    )
    assert ResponsesSseEvent(type="response.completed").is_terminal is True
    assert ResponsesSseEvent(type="response.failed").is_terminal is True
    assert ResponsesSseEvent(type="response.created").is_terminal is False
    assert TERMINAL_EVENTS.get("response.completed") is True
    assert TERMINAL_EVENTS.get("response.failed") is False
    assert TERMINAL_EVENTS.get("response.created") is None
