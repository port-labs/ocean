import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from utils.misc import CustomProperties, AsyncPaginator
from utils.resources import (
    resync_custom_kind,
    resync_cloudcontrol,
    resync_resource_group,
    resync_sqs_queue,
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
) -> None:
    """Test that resync_resource_group produces valid output."""
    mock_client = AsyncMock()

    mock_paginator = AsyncMock()

    async def mock_paginate_generator(
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"Groups": [{"GroupName": "test-group", "GroupArn": "test-group-arn"}]}

    mock_paginator.paginate = mock_paginate_generator

    mock_client.get_paginator.return_value = mock_paginator

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client
    mock_session.client.return_value = mock_context_manager

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


@pytest.mark.asyncio
async def test_resync_custom_kind_yields_empty_list_when_permission_denied(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_custom_kind yields empty list on permission denied."""
    from botocore.exceptions import ClientError

    # Arrange
    error_response = {"Error": {"Code": "AccessDenied"}}
    mock_client = AsyncMock()
    mock_client.describe_cache_clusters.side_effect = ClientError(
        error_response, "DescribeCacheClusters"
    )

    mock_exceptions = MagicMock()
    mock_exceptions.ClientError = ClientError
    mock_client.exceptions = mock_exceptions

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client

    # Act
    with patch.object(mock_session, "client", return_value=mock_context_manager):
        with patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ):
            results = []
            async for batch in resync_custom_kind(
                kind="AWS::ElastiCache::Cluster",
                session=mock_session,
                service_name="elasticache",
                describe_method="describe_cache_clusters",
                list_param="CacheClusters",
                marker_param="Marker",
            ):
                results.append(batch)

    # Assert
    assert len(results) == 1, "Should yield exactly one batch"
    assert results[0] == [], "Should yield empty list for permission denied"


@pytest.mark.asyncio
async def test_resync_cloudcontrol_yields_empty_list_when_permission_denied(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_cloudcontrol yields empty list on permission denied."""
    from botocore.exceptions import ClientError

    # Arrange
    error_response = {"Error": {"Code": "AccessDenied"}}
    mock_client = AsyncMock()

    mock_paginator = AsyncMock()

    async def mock_paginate_generator(**kwargs):
        raise ClientError(error_response, "ListResources")
        yield

    mock_paginator.paginate = mock_paginate_generator
    mock_client.get_paginator = MagicMock(return_value=mock_paginator)

    mock_exceptions = MagicMock()
    mock_exceptions.ClientError = ClientError
    mock_client.exceptions = mock_exceptions

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client

    # Act
    with patch.object(mock_session, "client", return_value=mock_context_manager):
        with patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ):
            results = []
            async for batch in resync_cloudcontrol(
                kind="AWS::S3::Bucket",
                session=mock_session,
                use_get_resource_api=False,
            ):
                results.append(batch)

    # Assert
    assert len(results) == 1, "Should yield exactly one batch"
    assert results[0] == [], "Should yield empty list for permission denied"


@pytest.mark.asyncio
async def test_resync_sqs_queue_yields_empty_list_when_permission_denied(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_sqs_queue yields empty list on permission denied."""
    from botocore.exceptions import ClientError

    # Arrange
    error_response = {"Error": {"Code": "AccessDenied"}}
    mock_client = AsyncMock()
    mock_client.list_queues.side_effect = ClientError(error_response, "ListQueues")

    mock_paginator = AsyncMock()

    async def mock_paginate_generator(**kwargs):
        raise ClientError(error_response, "ListQueues")
        yield

    mock_paginator.paginate = mock_paginate_generator
    mock_client.get_paginator = MagicMock(return_value=mock_paginator)

    mock_exceptions = MagicMock()
    mock_exceptions.ClientError = ClientError
    mock_client.exceptions = mock_exceptions

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client

    # Act
    with patch.object(mock_session, "client", return_value=mock_context_manager):
        with patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ):
            results = []
            async for batch in resync_sqs_queue(
                kind="AWS::SQS::Queue",
                session=mock_session,
            ):
                results.append(batch)

    # Assert
    assert len(results) == 1, "Should yield exactly one batch"
    assert results[0] == [], "Should yield empty list for permission denied"


@pytest.mark.asyncio
async def test_resync_resource_group_yields_empty_list_when_permission_denied(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_resource_group yields empty list on permission denied."""
    from botocore.exceptions import ClientError

    # Arrange
    error_response = {"Error": {"Code": "AccessDenied"}}
    mock_client = AsyncMock()

    mock_paginator = AsyncMock()

    async def mock_paginate_generator(**kwargs):
        raise ClientError(error_response, "ListGroups")
        yield

    mock_paginator.paginate = mock_paginate_generator
    mock_client.get_paginator = MagicMock(return_value=mock_paginator)

    mock_exceptions = MagicMock()
    mock_exceptions.ClientError = ClientError
    mock_client.exceptions = mock_exceptions

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client

    # Act
    with patch.object(mock_session, "client", return_value=mock_context_manager):
        with patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ):
            results = []
            async for batch in resync_resource_group(
                kind="AWS::ResourceGroups::Group",
                session=mock_session,
            ):
                results.append(batch)

    # Assert
    assert len(results) == 1, "Should yield exactly one batch"
    assert results[0] == [], "Should yield empty list for permission denied"


@pytest.mark.asyncio
async def test_resync_custom_kind_yields_resources_when_permission_granted(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_custom_kind yields resources when permission is granted."""
    # Arrange
    mock_client = AsyncMock()
    mock_response = {
        "CacheClusters": [
            {"CacheClusterId": "cluster1", "Engine": "redis"},
            {"CacheClusterId": "cluster2", "Engine": "redis"},
        ]
    }
    mock_client.describe_cache_clusters.return_value = mock_response

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client

    # Act
    with patch.object(mock_session, "client", return_value=mock_context_manager):
        with patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ):
            results = []
            async for batch in resync_custom_kind(
                kind="AWS::ElastiCache::Cluster",
                session=mock_session,
                service_name="elasticache",
                describe_method="describe_cache_clusters",
                list_param="CacheClusters",
                marker_param="Marker",
            ):
                results.append(batch)

    # Assert
    assert len(results) == 1, "Should yield exactly one batch"
    assert len(results[0]) == 2, "Should have 2 resources"
    assert results[0][0]["CacheClusterId"] == "cluster1"
    assert results[0][1]["CacheClusterId"] == "cluster2"


@pytest.mark.asyncio
async def test_resync_custom_kind_raises_exception_for_non_permission_errors(
    mock_session: AsyncMock,
    mock_account_id: str,
) -> None:
    """Test that resync_custom_kind raises exceptions for non-permission errors."""
    from botocore.exceptions import ClientError

    # Arrange
    error_response = {"Error": {"Code": "SomeOtherError"}}
    mock_client = AsyncMock()
    mock_client.describe_cache_clusters.side_effect = ClientError(
        error_response, "DescribeCacheClusters"
    )

    mock_exceptions = MagicMock()
    mock_exceptions.ClientError = ClientError
    mock_client.exceptions = mock_exceptions

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_client

    # Act & Assert
    with patch.object(mock_session, "client", return_value=mock_context_manager):
        with patch(
            "utils.resources._session_manager.find_account_id_by_session",
            return_value=mock_account_id,
        ):
            with pytest.raises(ClientError):
                async for batch in resync_custom_kind(
                    kind="AWS::ElastiCache::Cluster",
                    session=mock_session,
                    service_name="elasticache",
                    describe_method="describe_cache_clusters",
                    list_param="CacheClusters",
                    marker_param="Marker",
                ):
                    pass  # Should not reach here
