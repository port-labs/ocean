from datetime import UTC, datetime, timedelta

from azure_integration.foundry.helpers.utils import effective_conversation_cutoff
from azure_integration.foundry.helpers.responses_catalog import (
    merge_response_into_conversation_rollup,
)


def test_effective_cutoff_uses_since_days_only() -> None:
    before = datetime.now(UTC) - timedelta(days=366)
    cutoff = effective_conversation_cutoff(None, since_days=365)
    assert cutoff is not None
    assert cutoff > before


def test_effective_cutoff_uses_max_of_incremental_and_since() -> None:
    incremental = datetime(2026, 1, 1, tzinfo=UTC)
    cutoff = effective_conversation_cutoff(incremental, since_days=365)
    assert cutoff == incremental


def test_merge_response_into_conversation_rollup_dedupes_participants() -> None:
    rollup: dict[str, object] = {"id": "conv_1"}
    source = {
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        "output": [{"type": "mcp_call"}],
    }
    row = {
        "agent_id": "agent_a",
        "model_deployment_id": "gpt-4.1",
    }
    merge_response_into_conversation_rollup(rollup, row, source=source)
    merge_response_into_conversation_rollup(rollup, row, source=source)
    assert rollup["prompt_tokens"] == 20
    assert rollup["tool_call_count"] == 2
    assert rollup["participant_agent_ids"] == ["agent_a"]
    assert rollup["participant_model_deployment_ids"] == ["gpt-4.1"]
