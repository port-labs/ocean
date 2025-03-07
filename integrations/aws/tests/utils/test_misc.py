from utils.misc import (
    is_access_denied_exception,
    is_resource_not_found_exception,
    get_matching_kinds_and_blueprints_from_config,
    AsyncPaginator,
)
from typing import Optional, Dict, Any, AsyncGenerator
import unittest
from utils.overrides import AWSResourceConfig, AWSDescribeResourcesSelector
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import MagicMock, AsyncMock


class MockException(Exception):
    def __init__(self, response: Optional[Dict[str, Any]]) -> None:
        self.response = response


def test_access_denied_exception_with_response() -> None:
    e = MockException(response={"Error": {"Code": "AccessDenied"}})
    assert is_access_denied_exception(e)


def test_access_denied_exception_without_response() -> None:
    e = MockException(response=None)
    assert not is_access_denied_exception(e)


def test_access_denied_exception_with_other_error() -> None:
    e = MockException(response={"Error": {"Code": "SomeOtherError"}})
    assert not is_access_denied_exception(e)


def test_access_denied_exception_no_response_attribute() -> None:
    e = Exception("Test exception")
    assert not is_access_denied_exception(e)


def test_resource_not_found_exception_with_response() -> None:
    e = MockException(response={"Error": {"Code": "ResourceNotFoundException"}})
    assert is_resource_not_found_exception(e)


def test_resource_not_found_exception_without_response() -> None:
    e = MockException(response=None)
    assert not is_resource_not_found_exception(e)


def test_resource_not_found_exception_with_other_error() -> None:
    e = MockException(response={"Error": {"Code": "SomeOtherError"}})
    assert not is_resource_not_found_exception(e)


def test_resource_not_found_exception_no_response_attribute() -> None:
    e = Exception("Test exception")
    assert not is_resource_not_found_exception(e)


class TestGetMatchingKindsAndBlueprintsFromConfig(unittest.TestCase):

    def test_get_matching_kinds_and_blueprints(self) -> None:
        # Set up actual object instances
        selector = AWSDescribeResourcesSelector(query="true")
        entity = EntityMapping(
            identifier="lambda_function",
            blueprint="LambdaBlueprint",
        )
        mapping = MappingsConfig(mappings=entity)
        port_resource_config = PortResourceConfig(entity=mapping)

        resource_config = AWSResourceConfig(
            kind="AWS::Lambda::Function", selector=selector, port=port_resource_config
        )

        kind = "AWS::Lambda::Function"
        region = "us-west-1"
        resource_config_list = [resource_config]

        allowed_kinds, disallowed_kinds = get_matching_kinds_and_blueprints_from_config(
            kind, region, resource_config_list
        )

        self.assertEqual(allowed_kinds, {kind: ["LambdaBlueprint"]})
        self.assertEqual(disallowed_kinds, {})

    def test_no_matching_kind(self) -> None:
        selector = AWSDescribeResourcesSelector(query="true")
        entity = EntityMapping(
            identifier="AnotherIdentifier",
            blueprint="DifferentBlueprint",
        )
        mapping = MappingsConfig(mappings=entity)
        port_resource_config = PortResourceConfig(entity=mapping)

        resource_config = AWSResourceConfig(
            kind="AWS::SomeOther::Resource",
            selector=selector,
            port=port_resource_config,
        )

        kind = "AWS::Lambda::Function"
        region = "us-west-1"
        resource_config_list = [resource_config]

        allowed_kinds, disallowed_kinds = get_matching_kinds_and_blueprints_from_config(
            kind, region, resource_config_list
        )

        self.assertEqual(allowed_kinds, {})
        self.assertEqual(disallowed_kinds, {})


@pytest.mark.asyncio
class TestAsyncPaginator:
    async def test_async_paginator(self, mock_session: AsyncMock) -> None:
        async with mock_session.client("cloudcontrol") as client:
            paginator = AsyncPaginator(client, "list_resources", "ResourceDescriptions")
            results = []

            async for items in paginator.paginate(TypeName="AWS::S3::Bucket"):
                results.extend(items)

            assert len(results) == 1
            assert results[0]["Identifier"] == "test-id"

    async def test_async_paginator_with_batch_size(
        self, mock_session: AsyncMock
    ) -> None:
        async with mock_session.client("cloudcontrol") as client:
            paginator = AsyncPaginator(client, "list_resources", "ResourceDescriptions")
            batches = []

            async for batch in paginator.paginate(
                batch_size=1, TypeName="AWS::S3::Bucket"
            ):
                batches.append(batch)

            assert len(batches) == 1
            assert len(batches[0]) == 1
            assert batches[0][0]["Identifier"] == "test-id"

    async def test_async_paginator_empty_response(
        self, mock_session: AsyncMock
    ) -> None:
        async with mock_session.client("cloudcontrol") as client:
            # Override the paginator for this specific test
            class EmptyPaginatorMock:
                async def paginate(
                    self, **kwargs: Any
                ) -> AsyncGenerator[Dict[str, Any], None]:
                    yield {"ResourceDescriptions": []}

            client.get_paginator = MagicMock(return_value=EmptyPaginatorMock())

            paginator = AsyncPaginator(client, "list_resources", "ResourceDescriptions")
            results = []

            async for items in paginator.paginate(TypeName="AWS::S3::Bucket"):
                results.extend(items)

            assert len(results) == 0
