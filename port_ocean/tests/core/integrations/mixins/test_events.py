import pytest

from port_ocean.core.integrations.mixins.events import EventsMixin
from port_ocean.core.probe import ProbeContext


@pytest.mark.asyncio
async def test_on_probe_injects_context_and_returns_it_when_handler_returns_none() -> (
    None
):
    # Arrange
    mixin = EventsMixin()
    seen: dict[str, ProbeContext] = {}

    async def handler(context: ProbeContext) -> None:
        seen["context"] = context

    mixin.on_probe(handler)
    listener = mixin.event_strategy.on_probe
    assert listener is not None
    context = ProbeContext("probe-id")

    # Act
    returned = await listener(context)

    # Assert
    assert returned is None
    assert seen["context"] is context
    assert context.checks == []


@pytest.mark.asyncio
async def test_on_probe_uses_context_returned_by_handler() -> None:
    # Arrange
    mixin = EventsMixin()
    replacement = ProbeContext("replacement-id")

    async def handler(_context: ProbeContext) -> ProbeContext:
        return replacement

    mixin.on_probe(handler)
    listener = mixin.event_strategy.on_probe
    assert listener is not None

    # Act
    returned = await listener(ProbeContext("probe-id"))

    # Assert
    assert returned is replacement
