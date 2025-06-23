import pytest
from unittest.mock import AsyncMock, MagicMock
from utils.misc import CustomProperties, ResourceGroupsClientProtocol
from utils.resources import (
    resync_custom_kind,
    resync_cloudcontrol,
    resync_resource_group,
    enrich_group_with_resources,
    fetch_group_resources,
)
from typing import Any, AsyncGenerator, Dict, List
from tests.conftest import MockSTSClient, MockClient, MockPaginator


@pytest.fixture
def region() -> str:
    return "us-west-2"


@pytest.mark.asyncio
async def test_resync_custom_kind(
    mock_session: AsyncMock,
    region: str,
    mock_resource_config: MagicMock,
) -> None:
    """Test resync_custom_kind yields expected structure and values."""

    def create_client(service_name: str, *a: Any, **kw: Any) -> Any:
        if service_name == "sts":
            return MockSTSClient()
        return MockClient()

    mock_session.create_client = create_client
    results: List[Dict[str, Any]] = []
    async for batch in resync_custom_kind(
        kind="CustomKind",
        session=mock_session,
        region=region,
        service_name="cloudformation",
        describe_method="describe_stacks",
        list_param="Stacks",
        marker_param="NextToken",
        resource_config=mock_resource_config,
    ):
        results.extend(batch)
    assert results
    for item in results:
        assert item[CustomProperties.KIND.value] == "CustomKind"
        assert item[CustomProperties.ACCOUNT_ID.value] == "123456789012"
        assert item[CustomProperties.REGION.value] == region
        assert "StackName" in item
        assert item["StackName"] == "test-stack"


@pytest.mark.asyncio
async def test_resync_custom_kind_empty(
    mock_session: AsyncMock,
    region: str,
    mock_resource_config: MagicMock,
) -> None:
    """Test resync_custom_kind yields nothing for empty stacks."""

    class EmptyMockClient(MockClient):
        async def describe_stacks(self, **kwargs: Any) -> dict[str, Any]:
            return {"Stacks": [], "NextToken": None}

    def create_client(service_name: str, *a: Any, **kw: Any) -> Any:
        if service_name == "sts":
            return MockSTSClient()
        return EmptyMockClient()

    mock_session.create_client = create_client
    results: List[Any] = []
    async for batch in resync_custom_kind(
        kind="CustomKind",
        session=mock_session,
        region=region,
        service_name="cloudformation",
        describe_method="describe_stacks",
        list_param="Stacks",
        marker_param="NextToken",
        resource_config=mock_resource_config,
    ):
        results.extend(batch)
    assert results == []


@pytest.mark.asyncio
async def test_resync_cloudcontrol(
    mock_session: AsyncMock,
    region: str,
    mock_resource_config: MagicMock,
) -> None:
    """Test resync_cloudcontrol yields expected structure and values."""

    class CloudControlMockClient(MockClient):
        async def get_resource(self, **kwargs: Any) -> dict[str, Any]:
            return {"ResourceDescription": {"Identifier": "test-id", "Properties": "{}"}}

    def create_client(service_name: str, *a: Any, **kw: Any) -> Any:
        if service_name == "sts":
            return MockSTSClient()
        return CloudControlMockClient()

    mock_session.create_client = create_client
    results: List[Dict[str, Any]] = []
    async for batch in resync_cloudcontrol(
        kind="AWS::S3::Bucket",
        session=mock_session,
        region=region,
        resource_config=mock_resource_config,
    ):
        results.extend(batch)
    assert results
    for item in results:
        assert item[CustomProperties.KIND.value] == "AWS::S3::Bucket"
        assert item[CustomProperties.ACCOUNT_ID.value] == "123456789012"
        assert item[CustomProperties.REGION.value] == region
        assert "Identifier" in item
        assert "Properties" in item


@pytest.mark.asyncio
async def test_resync_resource_group(
    mock_session: AsyncMock,
    region: str,
) -> None:
    """Test resync_resource_group yields expected group structure."""

    class ResourceGroupMockClient(MockClient, ResourceGroupsClientProtocol):
        def get_paginator(self, name: str) -> MockPaginator:
            class GroupMockPaginator(MockPaginator):
                async def paginate(self, *args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
                    yield {"Groups": [{"Name": "group1", "GroupArn": "arn:aws:rg:group1"}]}
            return GroupMockPaginator()
        async def list_group_resources(self, *args: Any, **kwargs: Any) -> Any:
            return []
        async def list_groups(self, *args: Any, **kwargs: Any) -> Any:
            return []

    def create_client(service_name: str, *a: Any, **kw: Any) -> Any:
        if service_name == "sts":
            return MockSTSClient()
        return ResourceGroupMockClient()

    mock_session.create_client = create_client
    results: List[Any] = []
    async for batch in resync_resource_group(
        kind="ResourceGroupKind",
        session=mock_session,
        region=region,
    ):
        results.extend(batch)
    assert results
    for group in results:
        assert "Name" in group
        assert group["Name"] == "group1"
        assert group["GroupArn"] == "arn:aws:rg:group1"


@pytest.mark.asyncio
async def test_enrich_group_with_resources(
    region: str,
    mock_account_id: str,
) -> None:
    """Test enrich_group_with_resources yields expected enriched group."""

    class EnrichMockClient(MockClient, ResourceGroupsClientProtocol):
        def get_paginator(self, name: str) -> MockPaginator:
            class EnrichMockPaginator(MockPaginator):
                async def paginate(self, *args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
                    yield {"Resources": [{"ResourceArn": "arn:aws:ec2:instance/i-123"}]}
            return EnrichMockPaginator()
        async def list_group_resources(self, *args: Any, **kwargs: Any) -> Any:
            return []
        async def list_groups(self, *args: Any, **kwargs: Any) -> Any:
            return []

    mock_client: ResourceGroupsClientProtocol = EnrichMockClient()
    group = {"Name": "group1", "GroupArn": "arn:aws:rg:group1"}
    result = await enrich_group_with_resources(
        mock_client,
        group,
        kind="ResourceGroupKind",
        account_id=mock_account_id,
        region=region,
    )
    assert result[CustomProperties.KIND.value] == "ResourceGroupKind"
    assert result[CustomProperties.ACCOUNT_ID.value] == mock_account_id
    assert result[CustomProperties.REGION.value] == region
    assert result["Name"] == "group1"
    assert result["GroupArn"] == "arn:aws:rg:group1"
    assert "__Resources" in result
    assert result["__Resources"][0]["ResourceArn"] == "arn:aws:ec2:instance/i-123"


@pytest.mark.asyncio
async def test_fetch_group_resources(
    region: str,
) -> None:
    """Test fetch_group_resources returns a list of resources."""

    class FetchMockClient(MockClient, ResourceGroupsClientProtocol):
        def get_paginator(self, name: str) -> MockPaginator:
            class FetchMockPaginator(MockPaginator):
                async def paginate(self, *args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
                    yield {"ResourceDescriptions": [{"Identifier": "test-id"}]}
            return FetchMockPaginator()
        async def list_group_resources(self, *args: Any, **kwargs: Any) -> Any:
            return []
        async def list_groups(self, *args: Any, **kwargs: Any) -> Any:
            return []

    mock_client: ResourceGroupsClientProtocol = FetchMockClient()
    group_name = "group1"
    result = await fetch_group_resources(
        mock_client,
        group_name,
        region,
    )
    assert isinstance(result, list)
    if result:
        assert "Identifier" in result[0]


@pytest.mark.asyncio
async def test_fetch_group_resources_empty(
    region: str,
) -> None:
    """Test fetch_group_resources returns empty list for no resources."""

    class EmptyFetchMockClient(MockClient, ResourceGroupsClientProtocol):
        def get_paginator(self, name: str) -> MockPaginator:
            class EmptyFetchMockPaginator(MockPaginator):
                async def paginate(self, *args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
                    if False:
                        yield  # never yields
            return EmptyFetchMockPaginator()
        async def list_group_resources(self, *args: Any, **kwargs: Any) -> Any:
            return []
        async def list_groups(self, *args: Any, **kwargs: Any) -> Any:
            return []

    mock_client: ResourceGroupsClientProtocol = EmptyFetchMockClient()
    group_name = "group1"
    result = await fetch_group_resources(
        mock_client,
        group_name,
        region,
    )
    assert result == []
