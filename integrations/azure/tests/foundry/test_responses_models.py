from azure_integration.foundry.models.responses import (
    TERMINAL_EVENTS,
    Response,
    Usage,
)


def test_usage_dump_by_alias() -> None:
    usage = Usage.model_validate(
        {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
    ).model_dump()
    assert usage == {"inputTokens": 3, "outputTokens": 5, "totalTokens": 8}


def test_response_run_output() -> None:
    body = Response.model_validate(
        {
            "conversation_id": "conv_1",
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }
    )
    assert body.run_output(response_id="resp_1") == {
        "responseId": "resp_1",
        "conversationId": "conv_1",
        "inputTokens": 1,
        "outputTokens": 2,
        "totalTokens": 3,
    }


def test_terminal_events() -> None:
    assert TERMINAL_EVENTS["response.completed"] is True
    assert TERMINAL_EVENTS["response.failed"] is False
    assert "response.created" not in TERMINAL_EVENTS
