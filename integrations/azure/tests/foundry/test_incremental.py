from datetime import datetime, timezone

from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL


def test_agent_incremental_merge_params_empty_on_full_resync() -> None:
    assert AGENT_INCREMENTAL.merge_params({}, None) == {}


def test_agent_incremental_merge_params_with_cursor() -> None:
    cursor = datetime(2024, 1, 1, tzinfo=timezone.utc)
    params = AGENT_INCREMENTAL.merge_params({}, cursor)
    assert params["order"] == "desc"
