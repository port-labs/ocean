from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    with patch("port_ocean.helpers.async_client.ocean", mock_ocean):
        yield


def pytest_collection_modifyitems(session: Any, config: Any, items: Any) -> None:
    for item in items:
        item.add_marker(pytest.mark.httpx_mock(can_send_already_matched_responses=True))
