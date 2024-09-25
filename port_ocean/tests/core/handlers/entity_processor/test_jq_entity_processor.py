from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.ocean_types import CalculationResult


@pytest.fixture
def processor(monkeypatch: Any) -> JQEntityProcessor:
    mock_context = AsyncMock()
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return JQEntityProcessor(mock_context)


@pytest.mark.asyncio
async def test_compile(processor: JQEntityProcessor) -> None:
    pattern = ".foo"
    compiled = processor._compile(pattern)
    assert compiled is not None


@pytest.mark.asyncio
async def test_search(processor: JQEntityProcessor) -> None:
    data = {"foo": "bar"}
    pattern = ".foo"
    result = await processor._search(data, pattern)
    assert result == "bar"


@pytest.mark.asyncio
async def test_search_as_bool(processor: JQEntityProcessor) -> None:
    data = {"foo": True}
    pattern = ".foo"
    result = await processor._search_as_bool(data, pattern)
    assert result is True


@pytest.mark.asyncio
async def test_search_as_object(processor: JQEntityProcessor) -> None:
    data = {"foo": {"bar": "baz"}}
    obj = {"foo": ".foo.bar"}
    result = await processor._search_as_object(data, obj)
    assert result == {"foo": "baz"}


@pytest.mark.asyncio
async def test_get_mapped_entity(processor: JQEntityProcessor) -> None:
    data = {"foo": "bar"}
    raw_entity_mappings = {"foo": ".foo"}
    selector_query = '.foo == "bar"'
    result = await processor._get_mapped_entity(
        data, raw_entity_mappings, selector_query
    )
    assert result.entity == {"foo": "bar"}
    assert result.did_entity_pass_selector is True


@pytest.mark.asyncio
async def test_calculate_entity(processor: JQEntityProcessor) -> None:
    data = {"foo": "bar"}
    raw_entity_mappings = {"foo": ".foo"}
    selector_query = '.foo == "bar"'
    result, errors = await processor._calculate_entity(
        data, raw_entity_mappings, None, selector_query
    )
    assert len(result) == 1
    assert result[0].entity == {"foo": "bar"}
    assert result[0].did_entity_pass_selector is True
    assert not errors


@pytest.mark.asyncio
async def test_parse_items(processor: JQEntityProcessor) -> None:
    mapping = Mock()
    mapping.port.entity.mappings.dict.return_value = {
        "identifier": ".foo",
        "blueprint": ".foo",
        "properties": {"foo": ".foo"},
    }
    mapping.port.items_to_parse = None
    mapping.selector.query = '.foo == "bar"'
    raw_results = [{"foo": "bar"}]
    result = await processor._parse_items(mapping, raw_results)
    assert isinstance(result, CalculationResult)
    assert len(result.entity_selector_diff.passed) == 1
    assert result.entity_selector_diff.passed[0].properties.get("foo") == "bar"
    assert not result.errors
