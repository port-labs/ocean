import pytest
from unittest.mock import AsyncMock, patch
from utils.misc import CustomProperties, ResourceGroupsClientProtocol
from utils.resources import (
    resync_custom_kind,
    resync_cloudcontrol,
    resync_resource_group,
    enrich_group_with_resources,
    fetch_group_resources,
)
from typing import Any
from tests.conftest import MockSTSClient, MockClient, MockPaginator


@pytest.mark.asyncio
async def test_integration_resync_custom_kind_deep(
    mock_resource_config: Any, mock_account_id: str
) -> None:
    """High-level integration test for resync_custom_kind with deep structure validation."""
    mock_session = AsyncMock()
    region = "us-west-2"
    kind = "AWS::CloudFormation::Stack"
    with patch("utils.aws.get_sessions", return_value=iter([(mock_session, region)])):

        class CustomKindMockClient(MockClient):
            async def describe_stacks(self, **kwargs: Any) -> dict[str, Any]:
                return {
                    "Stacks": [{"StackName": "test-stack", "Foo": "Bar"}],
                    "NextToken": None,
                }

        def create_client(service_name: str, *a: Any, **kw: Any) -> Any:
            if service_name == "sts":
                return MockSTSClient()
            return CustomKindMockClient()

        mock_session.create_client = create_client
        results = []
        async for batch in resync_custom_kind(
            kind=kind,
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
        for resource in results:
            assert resource[CustomProperties.KIND.value] == kind
            assert resource[CustomProperties.ACCOUNT_ID.value] == mock_account_id
            assert resource[CustomProperties.REGION.value] == region
            assert resource["StackName"] == "test-stack"
            assert resource["Foo"] == "Bar"


@pytest.mark.asyncio
async def test_integration_resync_cloudcontrol_deep(
    mock_resource_config: Any, mock_account_id: str
) -> None:
    """High-level integration test for resync_cloudcontrol with deep structure validation."""
    mock_session = AsyncMock()
    region = "us-west-2"
    kind = "AWS::S3::Bucket"
    with patch("utils.aws.get_sessions", return_value=iter([(mock_session, region)])):

        class CloudControlMockClient(MockClient, ResourceGroupsClientProtocol):
            def get_paginator(self, name: str) -> MockPaginator:
                class CloudControlMockPaginator(MockPaginator):
                    async def paginate(self, *args: Any, **kwargs: Any) -> Any:
                        yield {
                            "ResourceDescriptions": [
                                {
                                    "Identifier": "test-id",
                                    "Properties": '{"Name": "bucket1"}',
                                }
                            ]
                        }

                return CloudControlMockPaginator()

            async def list_group_resources(self, *args: Any, **kwargs: Any) -> Any:
                return []

            async def list_groups(self, *args: Any, **kwargs: Any) -> Any:
                return []

        def create_client(service_name: str, *a: Any, **kw: Any) -> Any:
            if service_name == "sts":
                return MockSTSClient()
            return CloudControlMockClient()

        mock_session.create_client = create_client
        mock_resource_config.selector.use_get_resource_api = False
        results = []
        async for batch in resync_cloudcontrol(
            kind=kind,
            session=mock_session,
            region=region,
            resource_config=mock_resource_config,
        ):
            results.extend(batch)
        assert results
        for resource in results:
            assert resource[CustomProperties.KIND.value] == kind
            assert resource[CustomProperties.ACCOUNT_ID.value] == mock_account_id
            assert resource[CustomProperties.REGION.value] == region
            assert resource["Identifier"] == "test-id"
            assert resource["Properties"]["Name"] == "bucket1"


@pytest.mark.asyncio
async def test_integration_resync_resource_group_deep(mock_account_id: str) -> None:
    """High-level integration test for resync_resource_group with deep structure validation."""
    mock_session = AsyncMock()
    region = "us-west-2"
    kind = "ResourceGroupKind"
    with patch("utils.aws.get_sessions", return_value=iter([(mock_session, region)])):

        class ResourceGroupMockClient(MockClient, ResourceGroupsClientProtocol):
            def get_paginator(self, name: str) -> MockPaginator:
                class GroupMockPaginator(MockPaginator):
                    async def paginate(self, *args: Any, **kwargs: Any) -> Any:
                        yield {
                            "Groups": [
                                {"Name": "group1", "GroupArn": "arn:aws:rg:group1"}
                            ]
                        }

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
        results = []
        async for batch in resync_resource_group(
            kind=kind,
            session=mock_session,
            region=region,
        ):
            results.extend(batch)
        assert results
        for group in results:
            assert group[CustomProperties.KIND.value] == kind
            assert group[CustomProperties.ACCOUNT_ID.value] == mock_account_id
            assert group[CustomProperties.REGION.value] == region
            assert group["Name"] == "group1"
            assert group["GroupArn"] == "arn:aws:rg:group1"
            assert "__Resources" in group


@pytest.mark.asyncio
async def test_integration_enrich_group_with_resources_deep(
    mock_account_id: str,
) -> None:
    """High-level integration test for enrich_group_with_resources with deep structure validation."""
    region = "us-west-2"
    kind = "ResourceGroupKind"

    class EnrichMockClient(MockClient, ResourceGroupsClientProtocol):
        def get_paginator(self, name: str) -> MockPaginator:
            class EnrichMockPaginator(MockPaginator):
                async def paginate(self, *args: Any, **kwargs: Any) -> Any:
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
        kind=kind,
        account_id=mock_account_id,
        region=region,
    )
    assert result[CustomProperties.KIND.value] == kind
    assert result[CustomProperties.ACCOUNT_ID.value] == mock_account_id
    assert result[CustomProperties.REGION.value] == region
    assert result["Name"] == "group1"
    assert result["GroupArn"] == "arn:aws:rg:group1"
    assert "__Resources" in result
    assert result["__Resources"][0]["ResourceArn"] == "arn:aws:ec2:instance/i-123"


@pytest.mark.asyncio
async def test_integration_fetch_group_resources_deep() -> None:
    """High-level integration test for fetch_group_resources with deep structure validation."""
    region = "us-west-2"

    class FetchMockClient(MockClient, ResourceGroupsClientProtocol):
        def get_paginator(self, name: str) -> MockPaginator:
            class FetchMockPaginator(MockPaginator):
                async def paginate(self, *args: Any, **kwargs: Any) -> Any:
                    yield {"Resources": [{"ResourceArn": "arn:aws:ec2:instance/i-123"}]}

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
    assert result[0]["ResourceArn"] == "arn:aws:ec2:instance/i-123"
