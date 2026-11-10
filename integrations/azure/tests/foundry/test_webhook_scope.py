from azure_integration.foundry.helpers.webhook_scope import (
    build_response_external_id,
    extract_assistant_text_from_response,
    response_id_from_webhook_payload,
    usage_from_response,
)


def test_build_response_external_id() -> None:
    assert build_response_external_id("resp_abc") == "foundry_response_resp_abc"


def test_response_id_from_webhook_payload() -> None:
    payload = {
        "type": "response.completed",
        "data": {"response": {"id": "resp_1"}},
    }
    assert response_id_from_webhook_payload(payload) == "resp_1"


def test_extract_assistant_text() -> None:
    response = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Hello"}],
            }
        ]
    }
    assert extract_assistant_text_from_response(response) == "Hello"


def test_usage_from_response() -> None:
    usage = usage_from_response(
        {"usage": {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}}
    )
    assert usage["inputTokens"] == 3
    assert usage["totalTokens"] == 8
