# from typing import Any
# from unittest.mock import AsyncMock, Mock
#
# import pytest
#
# from port_ocean.context.ocean import PortOceanContext
# from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
#     JQEntityProcessor,
# )
# from port_ocean.core.ocean_types import CalculationResult
# from port_ocean.exceptions.core import EntityProcessorException
#
#
# @pytest.fixture
# def processor(monkeypatch: Any) -> JQEntityProcessor:
#     mock_context = AsyncMock()
#     monkeypatch.setattr(PortOceanContext, "app", mock_context)
#     return JQEntityProcessor(mock_context)
#
#
# @pytest.mark.asyncio
# async def test_compile(processor: JQEntityProcessor) -> None:
#     pattern = ".foo"
#     compiled = processor._compile(pattern)
#     assert compiled is not None
#
#
# @pytest.mark.asyncio
# async def test_search(processor: JQEntityProcessor) -> None:
#     data = {"foo": "bar"}
#     pattern = ".foo"
#     result = await processor._search(data, pattern)
#     assert result == "bar"
#
#
# @pytest.mark.asyncio
# async def test_search_as_bool(processor: JQEntityProcessor) -> None:
#     data = {"foo": True}
#     pattern = ".foo"
#     result = await processor._search_as_bool(data, pattern)
#     assert result is True
#
#
# @pytest.mark.asyncio
# async def test_search_as_object(processor: JQEntityProcessor) -> None:
#     data = {"foo": {"bar": "baz"}}
#     obj = {"foo": ".foo.bar"}
#     result = await processor._search_as_object(data, obj)
#     assert result == {"foo": "baz"}
#
#
# @pytest.mark.asyncio
# async def test_get_mapped_entity(processor: JQEntityProcessor) -> None:
#     data = {"foo": "bar"}
#     raw_entity_mappings = {"foo": ".foo"}
#     selector_query = '.foo == "bar"'
#     result = await processor._get_mapped_entity(
#         data, raw_entity_mappings, selector_query
#     )
#     assert result.entity == {"foo": "bar"}
#     assert result.did_entity_pass_selector is True
#
#
# @pytest.mark.asyncio
# async def test_calculate_entity(processor: JQEntityProcessor) -> None:
#     data = {"foo": "bar"}
#     raw_entity_mappings = {"foo": ".foo"}
#     selector_query = '.foo == "bar"'
#     result, errors = await processor._calculate_entity(
#         data, raw_entity_mappings, None, selector_query
#     )
#     assert len(result) == 1
#     assert result[0].entity == {"foo": "bar"}
#     assert result[0].did_entity_pass_selector is True
#     assert not errors
#
#
# @pytest.mark.asyncio
# async def test_parse_items(processor: JQEntityProcessor) -> None:
#     mapping = Mock()
#     mapping.port.entity.mappings.dict.return_value = {
#         "identifier": ".foo",
#         "blueprint": ".foo",
#         "properties": {"foo": ".foo"},
#     }
#     mapping.port.items_to_parse = None
#     mapping.selector.query = '.foo == "bar"'
#     raw_results = [{"foo": "bar"}]
#     result = await processor._parse_items(mapping, raw_results)
#     assert isinstance(result, CalculationResult)
#     assert len(result.entity_selector_diff.passed) == 1
#     assert result.entity_selector_diff.passed[0].properties.get("foo") == "bar"
#     assert not result.errors
#
#
# @pytest.mark.asyncio
# async def test_in_operator(processor: JQEntityProcessor) -> None:
#     data = {
#         "key": "GetPort_SelfService",
#         "name": "GetPort SelfService",
#         "desc": "Test",
#         "qualifier": "VW",
#         "visibility": "public",
#         "selectionMode": "NONE",
#         "subViews": [
#             {
#                 "key": "GetPort_SelfService_Second",
#                 "name": "GetPort SelfService Second",
#                 "qualifier": "SVW",
#                 "selectionMode": "NONE",
#                 "subViews": [
#                     {
#                         "key": "GetPort_SelfService_Third",
#                         "name": "GetPort SelfService Third",
#                         "qualifier": "SVW",
#                         "selectionMode": "NONE",
#                         "subViews": [],
#                         "referencedBy": [],
#                     },
#                     {
#                         "key": "Port_Test",
#                         "name": "Port Test",
#                         "qualifier": "SVW",
#                         "selectionMode": "NONE",
#                         "subViews": [],
#                         "referencedBy": [],
#                     },
#                 ],
#                 "referencedBy": [],
#             },
#             {
#                 "key": "Python",
#                 "name": "Python",
#                 "qualifier": "SVW",
#                 "selectionMode": "NONE",
#                 "subViews": [
#                     {
#                         "key": "Time",
#                         "name": "Time",
#                         "qualifier": "SVW",
#                         "selectionMode": "NONE",
#                         "subViews": [
#                             {
#                                 "key": "port_*****",
#                                 "name": "port-*****",
#                                 "qualifier": "SVW",
#                                 "selectionMode": "NONE",
#                                 "subViews": [
#                                     {
#                                         "key": "port_*****:REferenced",
#                                         "name": "REferenced",
#                                         "qualifier": "VW",
#                                         "visibility": "public",
#                                         "originalKey": "REferenced",
#                                     }
#                                 ],
#                                 "referencedBy": [],
#                             }
#                         ],
#                         "referencedBy": [],
#                     }
#                 ],
#                 "referencedBy": [],
#             },
#             {
#                 "key": "GetPort_SelfService:Authentication_Application",
#                 "name": "Authentication Application",
#                 "desc": "For auth services",
#                 "qualifier": "APP",
#                 "visibility": "private",
#                 "selectedBranches": ["main"],
#                 "originalKey": "Authentication_Application",
#             },
#         ],
#         "referencedBy": [],
#     }
#     pattern = '.subViews | map(select((.qualifier | IN("VW", "SVW"))) | .key)'
#     result = await processor._search(data, pattern)
#     assert result == ["GetPort_SelfService_Second", "Python"]
#
#
# @pytest.mark.asyncio
# async def test_failure_of_jq_expression(processor: JQEntityProcessor) -> None:
#     data = {"foo": "bar"}
#     pattern = ".foo."
#     result = await processor._search(data, pattern)
#     assert result is None
#
#
# @pytest.mark.asyncio
# async def test_search_as_object_failure(processor: JQEntityProcessor) -> None:
#     data = {"foo": {"bar": "baz"}}
#     obj = {"foo": ".foo.bar."}
#     result = await processor._search_as_object(data, obj)
#     assert result == {"foo": None}
#
#
# @pytest.mark.asyncio
# async def test_search_as_bool_failure(processor: JQEntityProcessor) -> None:
#     data = {"foo": "bar"}
#     pattern = ".foo"
#     with pytest.raises(
#         EntityProcessorException,
#         match="Expected boolean value, got <class 'str'> instead",
#     ):
#         await processor._search_as_bool(data, pattern)
#
#
# # test amount of time taken to search for a pattern for 100 raw entities
# @pytest.mark.asyncio
# async def test_search_performance_10000(processor: JQEntityProcessor) -> None:
#     data = {"foo": "bar"}
#     pattern = ".foo"
#     for _ in range(10000):
#         result = await processor._search(data, pattern)
#         assert result == "bar"
#
#
# @pytest.mark.asyncio
# async def test_parse_items_performance_10000(processor: JQEntityProcessor) -> None:
#     mapping = Mock()
#     mapping.port.entity.mappings.dict.return_value = {
#         "identifier": ".foo",
#         "blueprint": ".foo",
#         "properties": {"foo": ".foo"},
#     }
#     mapping.port.items_to_parse = None
#     mapping.selector.query = '.foo == "bar"'
#     raw_results = [{"foo": "bar"}]
#     for _ in range(10000):
#         result = await processor._parse_items(mapping, raw_results)
#         assert isinstance(result, CalculationResult)
#         assert len(result.entity_selector_diff.passed) == 1
#         assert result.entity_selector_diff.passed[0].properties.get("foo") == "bar"
#         assert not result.errors
