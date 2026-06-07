from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_init_client() -> Generator[None, None, None]:
    """Patch init_client in the base processor so processor fixtures can be created without
    real Datadog credentials.  Individual tests that need a specific client mock can
    override self.client on the already-constructed processor instance."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.base_processor.init_client",
        return_value=MagicMock(),
    ):
        yield
