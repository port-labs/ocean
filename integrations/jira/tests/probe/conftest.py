from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.core.probe import ProbeContext


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context
