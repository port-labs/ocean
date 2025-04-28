import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from utils.misc import CustomProperties, AsyncPaginator
from utils.resources import (
    resync_custom_kind,
    resync_cloudcontrol,
    resync_resource_group,
    enrich_group_with_resources,
    fetch_group_resources,
)
from typing import Any, AsyncGenerator, Dict


@pytest.mark.asyncio
async def test_resync_custom_kind(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_custom_kind produces valid output."""
    with patch(
        "utils.resources._session_manager.find_account_id_by_session",
        return_value=mock_account_id,
    ):
        async for result in resync_custom_kind(
            kind="AWS::CloudFormation::Stack",
            session=mock_session,
            service_name="cloudformation",
            describe_method="describe_method",
            list_param="ResourceList",
            marker_param="NextToken",
        ):
            assert isinstance(result, list)
            for resource in result:
                assert (
                    resource[CustomProperties.KIND.value]
                    == "AWS::CloudFormation::Stack"
                )
                assert resource[CustomProperties.ACCOUNT_ID.value] == mock_account_id
                assert resource[CustomProperties.REGION.value] == "us-west-2"
                assert "Properties" in resource


@pytest.mark.asyncio
async def test_resync_cloudcontrol(
    mock_session: AsyncMock,
    mock_account_id: str,
    mock_resource_config: MagicMock,
) -> None:
    """Test that resync_cloudcontrol produces valid output."""
    # Configure the mock resource config to use get_resource_api
    use_get_resource_api = True

    with patch(
        "utils.resources._session_manager.find_account_id_by_session",
        return_value=mock_account_id,
    ):
        async for result in resync_cloudcontrol(
            kind="AWS::S3::Bucket",
            session=mock_session,
            use_get_resource_api=use_get_resource_api,
        ):
            assert isinstance(result, list)
            for resource in result:
                assert resource[CustomProperties.KIND.value] == "AWS::S3::Bucket"
                assert resource[CustomProperties.ACCOUNT_ID.value] == mock_account_id
                assert resource[CustomProperties.REGION.value] == "us-west-2"
                assert "Properties" in resource


@pytest.mark.asyncio
async def test_resync_cloudcontrol_without_get_resource_api(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_cloudcontrol produces valid output when not using get_resource_api."""
    # Configure the mock resource config to not use get_resource_api
    use_get_resource_api = False

    with patch(
        "utils.resources._session_manager.find_account_id_by_session",
        return_value=mock_account_id,
    ):
        async for result in resync_cloudcontrol(
            kind="AWS::S3::Bucket",
            session=mock_session,
            use_get_resource_api=use_get_resource_api,
        ):
            assert isinstance(result, list)
            for resource in result:
                assert resource[CustomProperties.KIND.value] == "AWS::S3::Bucket"
                assert resource[CustomProperties.ACCOUNT_ID.value] == mock_account_id
                assert resource[CustomProperties.REGION.value] == "us-west-2"
                assert "Properties" in resource


@pytest.mark.asyncio
async def test_fetch_group_resources(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that fetch_group_resources correctly retrieves resources for a group."""
    # Create a mock client
    mock_client = AsyncMock()

    # Create a mock AsyncPaginator
    mock_paginator = AsyncMock(spec=AsyncPaginator)

    # Create a mock paginate method that returns an async generator
    async def mock_paginate_generator(
        **kwargs: Any,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [
            {
                "ResourceArn": "arn:aws:ec2:us-west-2:123456789012:instance/i-1234567890abcdef0"
            }
        ]

    # Set up the paginator's paginate method
    mock_paginator.paginate = mock_paginate_generator

    # Patch the AsyncPaginator class to return our mock
    with patch("utils.resources.AsyncPaginator", return_value=mock_paginator):
        # Call the function
        resources = await fetch_group_resources(mock_client, "test-group", "us-west-2")

        # Verify the results
        assert len(resources) == 1
        assert (
            resources[0]["ResourceArn"]
            == "arn:aws:ec2:us-west-2:123456789012:instance/i-1234567890abcdef0"
        )


@pytest.mark.asyncio
async def test_enrich_group_with_resources(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that enrich_group_with_resources correctly enriches a group with its resources."""
    # Mock the client
    mock_client = AsyncMock()

    # Mock the fetch_group_resources function
    with patch(
        "utils.resources.fetch_group_resources",
        return_value=[{"ResourceArn": "test-arn"}],
    ):
        # Test data
        group = {"Name": "test-group", "GroupArn": "test-group-arn"}
        kind = "AWS::ResourceGroups::Group"
        region = "us-west-2"

        # Call the function
        result = await enrich_group_with_resources(
            mock_client, group, kind, mock_account_id, region
        )

        # Verify the results
        assert result[CustomProperties.KIND.value] == kind
        assert result[CustomProperties.ACCOUNT_ID.value] == mock_account_id
        assert result[CustomProperties.REGION.value] == region
        assert result["Name"] == "test-group"
        assert result["GroupArn"] == "test-group-arn"
        assert result["__Resources"] == [{"ResourceArn": "test-arn"}]


@pytest.mark.asyncio
async def test_resync_resource_group(
    mock_session: AsyncMock,
    mock_account_id: str,
    mock_resource_config: MagicMock,
) -> None:
    """Test that resync_resource_group produces valid output."""
    # Create a mock client with a properly configured paginator
    mock_client = AsyncMock()

    # Create a mock paginator with a properly configured paginate method
    mock_paginator = AsyncMock()

    # Create a mock paginate method that returns an async generator
    async def mock_paginate_generator(
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"Groups": [{"GroupName": "test-group", "GroupArn": "test-group-arn"}]}

    # Set up the paginator's paginate method
    mock_paginator.paginate = mock_paginate_generator

    # Set up the client's get_paginator method
    mock_client.get_paginator.return_value = mock_paginator

    # Set up the session's client method to return a context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client
    mock_session.client.return_value = mock_context_manager

    # Mock the enrich_group_with_resources function
    with (
        patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ),
        patch(
            "utils.resources.enrich_group_with_resources",
            return_value={
                CustomProperties.KIND.value: "AWS::ResourceGroups::Group",
                CustomProperties.ACCOUNT_ID.value: mock_account_id,
                CustomProperties.REGION.value: "us-west-2",
                "GroupName": "test-group",
                "GroupArn": "test-group-arn",
                "__Resources": [{"ResourceArn": "test-arn"}],
            },
        ),
    ):
        async for result in resync_resource_group(
            kind="AWS::ResourceGroups::Group",
            session=mock_session,
            resource_config=mock_resource_config,
        ):
            assert isinstance(result, list)
            assert len(result) == 1
            group = result[0]
            assert group[CustomProperties.KIND.value] == "AWS::ResourceGroups::Group"
            assert group[CustomProperties.ACCOUNT_ID.value] == mock_account_id
            assert group[CustomProperties.REGION.value] == "us-west-2"
            assert group["GroupName"] == "test-group"
            assert group["GroupArn"] == "test-group-arn"
            assert group["__Resources"] == [{"ResourceArn": "test-arn"}]
