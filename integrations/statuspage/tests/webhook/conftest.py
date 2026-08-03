from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_statuspage_client() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    with patch(
        "webhook.webhook_processors.base_webhook_processor.init_client",
        return_value=mock_client,
    ):
        yield mock_client
