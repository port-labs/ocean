import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from utils.misc import CustomProperties
from utils.resources import (
    resync_custom_kind,
    resync_cloudcontrol,
)


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
    mock_resource_config: MagicMock,
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
