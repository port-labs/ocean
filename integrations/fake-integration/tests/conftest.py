from typing import Any, Generator

from port_ocean.tests.helpers.fixtures import (
    get_mocked_ocean_app,
    get_mock_ocean_resource_configs,
)
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock Port Ocean context so OceanAsyncClient can be used without initializing the app."""
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    with patch("port_ocean.helpers.async_client.ocean", mock_ocean):
        yield


def pytest_collection_modifyitems(session: Any, config: Any, items: Any) -> None:
    for item in items:
        # This allows us to re-requestd the same mocked endpoint several times
        item.add_marker(pytest.mark.httpx_mock(can_send_already_matched_responses=True))


# ruff: noqa
