from types import SimpleNamespace
from unittest.mock import patch

from port_ocean.rate_limiting.models import SyncTier
from port_ocean.rate_limiting.tier import derive_sync_tier


def test_derive_sync_tier_resync_is_low() -> None:
    listener = SimpleNamespace(
        should_resync=True,
        should_process_webhooks=False,
        should_run_actions=False,
    )
    with patch("port_ocean.helpers.sync_tier.ocean") as mock_ocean:
        mock_ocean.config.event_listener = listener
        mock_ocean.config.integration.incremental_sync_enabled = False
        assert derive_sync_tier() == SyncTier.LOW
