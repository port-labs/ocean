from datetime import UTC, datetime, timedelta

from azure_integration.foundry.foundry_incremental import (
    AGENT_INCREMENTAL,
    CONVERSATION_INCREMENTAL,
    MEMORY_STORE_INCREMENTAL,
    MODEL_DEPLOYMENT_INCREMENTAL,
    RESPONSE_INCREMENTAL,
)


def test_order_desc_kinds_always_send_order() -> None:
    """APIs that support order=desc must send it even with no watermark (sinceDays)."""
    for strategy in (
        AGENT_INCREMENTAL,
        CONVERSATION_INCREMENTAL,
        RESPONSE_INCREMENTAL,
        MEMORY_STORE_INCREMENTAL,
    ):
        assert strategy.merge_params({}, None) == {"order": "desc"}
        assert strategy.merge_params({"limit": 50}, None) == {
            "limit": 50,
            "order": "desc",
        }


def test_deployments_have_no_cutoff_strategy() -> None:
    """Deployments list has no order/timestamps — exporter must full-scan."""
    assert MODEL_DEPLOYMENT_INCREMENTAL is None


def test_agent_stop_uses_created_at_matching_api_order() -> None:
    assert AGENT_INCREMENTAL._stop_field == "created_at"


def test_cutoff_stops_on_older_created_at() -> None:
    cursor = datetime(2026, 1, 10, tzinfo=UTC)
    assert RESPONSE_INCREMENTAL.should_stop(
        {"id": "old", "created_at": datetime(2026, 1, 1, tzinfo=UTC).timestamp()},
        cursor,
    )
    assert not RESPONSE_INCREMENTAL.should_stop(
        {"id": "new", "created_at": datetime(2026, 1, 15, tzinfo=UTC).timestamp()},
        cursor,
    )


def test_agent_stop_falls_back_to_versions_latest_created_at() -> None:
    cursor = datetime.now(UTC) - timedelta(days=1)
    old = (cursor - timedelta(days=5)).timestamp()
    assert AGENT_INCREMENTAL.should_stop(
        {"id": "a", "versions": {"latest": {"created_at": old}}},
        cursor,
    )
