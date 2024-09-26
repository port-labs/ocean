from typing import Any
from unittest.mock import MagicMock


async def test_cache_coroutine_result(monkeypatch: Any) -> None:
    # Arrange
    from port_ocean.utils.cache import cache_coroutine_result

    attributes_mock = MagicMock()
    attributes_mock.attributes = {}
    monkeypatch.setattr("port_ocean.utils.cache.event", attributes_mock)

    @cache_coroutine_result()
    async def test_coroutine() -> Any:
        return "test"

    # Act
    await test_coroutine()

    # Assert
    assert "test_coroutine" in list(attributes_mock.attributes.keys())[0]
