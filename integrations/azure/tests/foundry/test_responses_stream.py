from azure_integration.foundry.helpers.responses_stream import (
    format_responses_sse_log_message,
    parse_responses_sse_payload,
    response_id_from_sse_event,
)


def test_parse_responses_sse_payload_invalid() -> None:
    assert parse_responses_sse_payload("not-json") is None


def test_format_skips_noise_events() -> None:
    assert (
        format_responses_sse_log_message(
            {"type": "response.created", "response": {"id": "r1"}}
        )
        is None
    )
    assert (
        format_responses_sse_log_message(
            {"type": "response.output_text.delta", "delta": "Hi"}
        )
        is None
    )


def test_format_output_text_done() -> None:
    message = format_responses_sse_log_message(
        {
            "type": "response.output_text.done",
            "text": "Hey! How can I help you today?",
        }
    )
    assert message == "Hey! How can I help you today?"


def test_format_completed_usage() -> None:
    message = format_responses_sse_log_message(
        {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        }
    )
    assert message == "Response completed (inputTokens=10, outputTokens=5, totalTokens=15)"


def test_response_id_from_sse_created() -> None:
    assert (
        response_id_from_sse_event(
            {
                "type": "response.created",
                "response": {"id": "resp_xyz"},
            }
        )
        == "resp_xyz"
    )
