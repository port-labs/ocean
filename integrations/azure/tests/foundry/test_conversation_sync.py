from datetime import UTC, datetime, timedelta

from azure_integration.foundry.helpers.utils import effective_conversation_cutoff


def test_effective_cutoff_uses_since_days_only() -> None:
    before = datetime.now(UTC) - timedelta(days=31)
    cutoff = effective_conversation_cutoff(None, since_days=30)
    assert cutoff is not None
    assert cutoff > before


def test_effective_cutoff_uses_max_of_incremental_and_since() -> None:
    incremental = datetime.now(UTC) - timedelta(days=2)
    cutoff = effective_conversation_cutoff(incremental, since_days=30)
    assert cutoff == incremental
