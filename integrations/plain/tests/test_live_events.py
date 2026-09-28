from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml  # type: ignore[import-untyped]
from port_ocean.config.dynamic import default_config_factory
from port_ocean.context.ocean import ocean

from main import on_start

PHASE_ONE_KINDS = ("company", "tenant", "user", "customer", "thread")


def test_spec_accepts_enable_live_events_default_false() -> None:
    spec = yaml.safe_load(Path(".port/spec.yaml").read_text())
    resources = spec["features"][0]["resources"]
    kinds = [resource["kind"] for resource in resources]
    for kind in PHASE_ONE_KINDS:
        assert kind in kinds

    model = default_config_factory(spec["configurations"])
    config = model(api_token="plainApiKey_test")
    dumped: dict[str, Any] = config.model_dump()

    assert dumped["enable_live_events"] is False
    assert dumped["api_url"] == "https://core-api.uk.plain.com/graphql/v1"
    assert dumped["page_size"] == "100"


@pytest.mark.parametrize("raw", [False, "false", None])
async def test_on_start_does_not_register_webhooks_when_live_events_disabled(
    raw: bool | str | None,
) -> None:
    original = ocean.app.config.integration.config
    config: dict[str, Any] = {"api_token": "plainApiKey_test"}
    if raw is not None:
        config["enable_live_events"] = raw
    ocean.app.config.integration.config = config
    try:
        with patch("main._register_webhook_target", new_callable=AsyncMock) as register:
            assert on_start is not None
            await on_start()
        register.assert_not_awaited()
    finally:
        ocean.app.config.integration.config = original
