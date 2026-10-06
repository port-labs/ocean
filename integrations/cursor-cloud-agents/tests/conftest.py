"""Pytest configuration and fixtures."""

from collections.abc import Generator
from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest
import port_ocean.utils.cache as cache_module


def _noop_cache_iterator_result(*_args: Any, **_kwargs: Any) -> Callable[[Any], Any]:
    def decorator(fn: Any) -> Any:
        return fn

    return decorator


cache_module.cache_iterator_result = _noop_cache_iterator_result


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock Port Ocean context so the integration modules can run in tests."""
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    mock_ocean.config.client_timeout = 60
    with patch("port_ocean.helpers.async_client.ocean", mock_ocean, create=True):
        yield
