from typing import Any

from port_ocean.tests.helpers.fixtures import (
    get_mocked_ocean_app,
    get_mock_ocean_resource_configs,
)
import pytest


def pytest_collection_modifyitems(session: Any, config: Any, items: Any) -> None:
    for item in items:
        # This allows us to re-requestd the same mocked endpoint several times
        item.add_marker(pytest.mark.httpx_mock(can_send_already_matched_responses=True))


# ruff: noqa
