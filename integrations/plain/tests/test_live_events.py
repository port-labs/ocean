from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import yaml  # type: ignore[import-untyped]
from port_ocean.config.dynamic import default_config_factory
from port_ocean.context.ocean import ocean

from main import on_start

ALL_KINDS = (
    "company",
    "tenant",
    "user",
    "customer",
    "thread",
    "thread-message",
    "discussion",
    "discussion-message",
)


def test_spec_accepts_webhook_secret() -> None:
    spec = yaml.safe_load(Path(".port/spec.yaml").read_text())
    resources = spec["features"][0]["resources"]
    kinds = [resource["kind"] for resource in resources]
    for kind in ALL_KINDS:
        assert kind in kinds

    config_names = {item["name"] for item in spec["configurations"]}
    assert "enableLiveEvents" not in config_names

    model = default_config_factory(spec["configurations"])
    config = model(api_token="plainApiKey_test")
    dumped: dict[str, Any] = config.model_dump()

    assert "enable_live_events" not in dumped
    assert dumped.get("webhook_secret") in (None, "")
    assert dumped["api_url"] == "https://core-api.uk.plain.com/graphql/v1"
    assert dumped["page_size"] == "100"


async def test_on_start_does_not_register_webhooks_when_listener_disables_them() -> (
    None
):
    original = ocean.app.config.event_listener.should_process_webhooks
    ocean.app.config.event_listener.should_process_webhooks = False
    try:
        with patch("main.register_webhook_target", new_callable=AsyncMock) as register:
            assert on_start is not None
            await on_start()
        register.assert_not_awaited()
    finally:
        ocean.app.config.event_listener.should_process_webhooks = original
