from azure_integration.foundry.helpers.webhook_scope import (
    FoundryResponseBody,
    response_id_from_webhook_payload,
    usage_from_response,
)


def test_response_id_from_webhook_payload() -> None:
    payload = {
        "type": "response.completed",
        "data": {"response": {"id": "resp_1"}},
    }
    assert response_id_from_webhook_payload(payload) == "resp_1"


def test_assistant_text() -> None:
    body = FoundryResponseBody.model_validate(
        {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Hello"}],
                }
            ]
        }
    )
    assert body.assistant_text() == "Hello"


def test_usage_from_response() -> None:
    usage = usage_from_response(
        {"usage": {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}}
    )
    assert usage["inputTokens"] == 3
    assert usage["totalTokens"] == 8


def test_usage_from_response_sums_when_total_missing() -> None:
    usage = usage_from_response(
        {"usage": {"input_tokens": 3, "output_tokens": 5}}
    )
    assert usage["totalTokens"] == 8


def test_invoke_run_output_prefers_body_status_and_conversation() -> None:
    slim, success = FoundryResponseBody.invoke_run_output(
        response_id="resp_1",
        display_body={
            "status": "failed",
            "conversation": {"id": "conv_new"},
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "nope"}],
                }
            ],
        },
        prior_conversation_id="conv_old",
    )
    assert success is False
    assert slim == {
        "responseId": "resp_1",
        "conversationId": "conv_new",
        "inputTokens": 1,
        "outputTokens": 2,
        "totalTokens": 3,
        "answer": "nope",
    }
