from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.s3.bucket.actions import (
    GetBucketPublicAccessBlockAction,
    GetBucketOwnershipControlsAction,
    GetBucketEncryptionAction,
    GetBucketTaggingAction,
)
from aws.core.interfaces.action import Action

# Type ignore for mock S3 client methods throughout this file
# mypy: disable-error-code=attr-defined


class TestGetBucketPublicAccessBlockAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the S3 methods to avoid attribute errors
        mock_client.get_public_access_block = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetBucketPublicAccessBlockAction:
        """Create a GetBucketPublicAccessBlockAction instance for testing."""
        return GetBucketPublicAccessBlockAction(mock_client)

    def test_inheritance(self, action: GetBucketPublicAccessBlockAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetBucketPublicAccessBlockAction
    ) -> None:
        """Test successful execution of get_public_access_block."""
        # Mock response
        expected_response = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            }
        }
        action.client.get_public_access_block.return_value = expected_response

        # Execute
        result = await action.execute("test-bucket")

        # Verify
        expected_result = {
            "Name": "test-bucket",
            "PublicAccessBlockConfiguration": expected_response[
                "PublicAccessBlockConfiguration"
            ],
        }
        assert result == expected_result

        # Verify client was called correctly
        action.client.get_public_access_block.assert_called_once_with(
            Bucket="test-bucket"
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched bucket public access block for bucket test-bucket"
        )

    @pytest.mark.asyncio
    async def test_execute_different_bucket(
        self, action: GetBucketPublicAccessBlockAction
    ) -> None:
        """Test execution with different bucket name."""
        expected_response = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }
        action.client.get_public_access_block.return_value = expected_response

        result = await action.execute("prod-bucket")

        assert result == {
            "Name": "prod-bucket",
            "PublicAccessBlockConfiguration": expected_response[
                "PublicAccessBlockConfiguration"
            ],
        }
        action.client.get_public_access_block.assert_called_once_with(
            Bucket="prod-bucket"
        )


class TestGetBucketOwnershipControlsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.get_bucket_ownership_controls = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetBucketOwnershipControlsAction:
        """Create a GetBucketOwnershipControlsAction instance for testing."""
        return GetBucketOwnershipControlsAction(mock_client)

    def test_inheritance(self, action: GetBucketOwnershipControlsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetBucketOwnershipControlsAction
    ) -> None:
        """Test successful execution of get_bucket_ownership_controls."""
        expected_response = {
            "OwnershipControls": {
                "Rules": [{"ObjectOwnership": "BucketOwnerPreferred"}]
            }
        }
        action.client.get_bucket_ownership_controls.return_value = expected_response

        result = await action.execute("test-bucket")

        assert result == {
            "Name": "test-bucket",
            "OwnershipControls": expected_response["OwnershipControls"],
        }
        action.client.get_bucket_ownership_controls.assert_called_once_with(
            Bucket="test-bucket"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched bucket ownership controls for bucket test-bucket"
        )


class TestGetBucketEncryptionAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.get_bucket_encryption = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetBucketEncryptionAction:
        """Create a GetBucketEncryptionAction instance for testing."""
        return GetBucketEncryptionAction(mock_client)

    def test_inheritance(self, action: GetBucketEncryptionAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetBucketEncryptionAction
    ) -> None:
        """Test successful execution of get_bucket_encryption."""
        expected_response = {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": "arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012",
                        },
                        "BucketKeyEnabled": True,
                    }
                ]
            }
        }
        action.client.get_bucket_encryption.return_value = expected_response

        result = await action.execute("encrypted-bucket")

        assert result == {
            "Name": "encrypted-bucket",
            "BucketEncryption": expected_response["ServerSideEncryptionConfiguration"],
        }
        action.client.get_bucket_encryption.assert_called_once_with(
            Bucket="encrypted-bucket"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched bucket encryption for bucket encrypted-bucket"
        )

    @pytest.mark.asyncio
    async def test_execute_no_encryption(
        self, action: GetBucketEncryptionAction
    ) -> None:
        """Test execution when bucket has no encryption configuration."""
        expected_response: dict[str, Any] = {
            "ServerSideEncryptionConfiguration": {"Rules": []}
        }
        action.client.get_bucket_encryption.return_value = expected_response

        result = await action.execute("unencrypted-bucket")

        assert result == {
            "Name": "unencrypted-bucket",
            "BucketEncryption": {"Rules": []},
        }
        action.client.get_bucket_encryption.assert_called_once_with(
            Bucket="unencrypted-bucket"
        )


class TestGetBucketTaggingAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the S3 methods and exceptions
        mock_client.get_bucket_tagging = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetBucketTaggingAction:
        """Create a GetBucketTaggingAction instance for testing."""
        return GetBucketTaggingAction(mock_client)

    def test_inheritance(self, action: GetBucketTaggingAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetBucketTaggingAction
    ) -> None:
        """Test successful execution of get_bucket_tagging."""
        expected_response = {
            "TagSet": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Project", "Value": "web-app"},
                {"Key": "Owner", "Value": "devops-team"},
            ]
        }
        action.client.get_bucket_tagging.return_value = expected_response

        result = await action.execute("tagged-bucket")

        assert result == {"Name": "tagged-bucket", "Tags": expected_response["TagSet"]}
        action.client.get_bucket_tagging.assert_called_once_with(Bucket="tagged-bucket")

        mock_logger.info.assert_called_once_with(
            "Successfully fetched bucket tagging for bucket tagged-bucket"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.actions.logger")
    async def test_execute_empty_tags(
        self, mock_logger: MagicMock, action: GetBucketTaggingAction
    ) -> None:
        """Test execution when bucket has empty TagSet."""
        expected_response: dict[str, Any] = {"TagSet": []}
        action.client.get_bucket_tagging.return_value = expected_response

        result = await action.execute("no-tags-bucket")

        assert result == {"Name": "no-tags-bucket", "Tags": []}
        action.client.get_bucket_tagging.assert_called_once_with(
            Bucket="no-tags-bucket"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched bucket tagging for bucket no-tags-bucket"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.actions.logger")
    async def test_execute_missing_tagset(
        self, mock_logger: MagicMock, action: GetBucketTaggingAction
    ) -> None:
        """Test execution when response doesn't contain TagSet."""
        expected_response: dict[str, Any] = {}  # No TagSet key
        action.client.get_bucket_tagging.return_value = expected_response

        result = await action.execute("missing-tagset-bucket")

        assert result == {"Name": "missing-tagset-bucket", "Tags": []}
        action.client.get_bucket_tagging.assert_called_once_with(
            Bucket="missing-tagset-bucket"
        )

    @pytest.mark.asyncio
    async def test_execute_no_such_tagset_error(
        self, action: GetBucketTaggingAction
    ) -> None:
        """Test execution when bucket has no tag set (NoSuchTagSet error)."""
        # Create a proper ClientError exception
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "NoSuchTagSet", "Message": "The TagSet does not exist"}
        }
        client_error = ClientError(error_response, "GetBucketTagging")  # type: ignore
        action.client.get_bucket_tagging.side_effect = client_error

        result = await action.execute("no-tagset-bucket")

        assert result == {"Name": "no-tagset-bucket", "Tags": []}
        action.client.get_bucket_tagging.assert_called_once_with(
            Bucket="no-tagset-bucket"
        )

    @pytest.mark.asyncio
    async def test_execute_other_client_error(
        self, action: GetBucketTaggingAction
    ) -> None:
        """Test execution when a different ClientError occurs."""
        # Create a proper ClientError exception for a different error
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        client_error = ClientError(error_response, "GetBucketTagging")  # type: ignore
        action.client.get_bucket_tagging.side_effect = client_error

        # Should re-raise the error for non-NoSuchTagSet errors
        with pytest.raises(ClientError) as exc_info:
            await action.execute("access-denied-bucket")

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
        action.client.get_bucket_tagging.assert_called_once_with(
            Bucket="access-denied-bucket"
        )

    @pytest.mark.asyncio
    async def test_execute_non_client_error(
        self, action: GetBucketTaggingAction
    ) -> None:
        """Test execution when a non-ClientError exception occurs."""
        action.client.get_bucket_tagging.side_effect = Exception("Network error")

        # Should re-raise non-ClientError exceptions
        with pytest.raises(Exception, match="Network error"):
            await action.execute("network-error-bucket")

        action.client.get_bucket_tagging.assert_called_once_with(
            Bucket="network-error-bucket"
        )


class TestAllActionsIntegration:
    """Integration tests for all actions working together."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add all S3 methods
        mock_client.get_public_access_block = AsyncMock()
        mock_client.get_bucket_ownership_controls = AsyncMock()
        mock_client.get_bucket_encryption = AsyncMock()
        mock_client.get_bucket_tagging = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.mark.asyncio
    async def test_all_actions_execution(self, mock_client: AsyncMock) -> None:
        """Test that all actions can be executed successfully."""
        # Setup responses for all actions
        mock_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {"BlockPublicAcls": True}
        }
        mock_client.get_bucket_ownership_controls.return_value = {
            "OwnershipControls": {
                "Rules": [{"ObjectOwnership": "BucketOwnerPreferred"}]
            }
        }
        mock_client.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {"Rules": []}
        }
        mock_client.get_bucket_tagging.return_value = {
            "TagSet": [{"Key": "Environment", "Value": "test"}]
        }

        # Create all actions
        actions = [
            GetBucketPublicAccessBlockAction(mock_client),
            GetBucketOwnershipControlsAction(mock_client),
            GetBucketEncryptionAction(mock_client),
            GetBucketTaggingAction(mock_client),
        ]

        # Execute all actions
        results = []
        for action in actions:
            result = await action.execute("integration-bucket")
            results.append(result)

        # Verify all results
        assert len(results) == 4
        assert "Name" in results[0] and "PublicAccessBlockConfiguration" in results[0]
        assert "Name" in results[1] and "OwnershipControls" in results[1]
        assert "Name" in results[2] and "BucketEncryption" in results[2]
        assert "Name" in results[3] and "Tags" in results[3]

        # Verify all client methods were called
        mock_client.get_public_access_block.assert_called_once_with(
            Bucket="integration-bucket"
        )
        mock_client.get_bucket_ownership_controls.assert_called_once_with(
            Bucket="integration-bucket"
        )
        mock_client.get_bucket_encryption.assert_called_once_with(
            Bucket="integration-bucket"
        )
        mock_client.get_bucket_tagging.assert_called_once_with(
            Bucket="integration-bucket"
        )

    @pytest.mark.asyncio
    async def test_actions_with_mixed_success_failure(
        self, mock_client: AsyncMock
    ) -> None:
        """Test actions with some succeeding and some failing."""
        # Setup mixed responses - some succeed, some fail
        mock_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {"BlockPublicAcls": True}
        }
        mock_client.get_bucket_ownership_controls.side_effect = Exception(
            "Access denied"
        )
        mock_client.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {"Rules": []}
        }

        # NoSuchTagSet error for tagging
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "NoSuchTagSet", "Message": "No tags"}}
        client_error = ClientError(error_response, "GetBucketTagging")  # type: ignore
        mock_client.get_bucket_tagging.side_effect = client_error

        # Create actions
        public_access_action = GetBucketPublicAccessBlockAction(mock_client)
        ownership_action = GetBucketOwnershipControlsAction(mock_client)
        encryption_action = GetBucketEncryptionAction(mock_client)
        tagging_action = GetBucketTaggingAction(mock_client)

        # Execute actions and handle exceptions
        public_access_result = await public_access_action.execute("mixed-bucket")

        with pytest.raises(Exception, match="Access denied"):
            await ownership_action.execute("mixed-bucket")

        encryption_result = await encryption_action.execute("mixed-bucket")
        tagging_result = await tagging_action.execute(
            "mixed-bucket"
        )  # Should handle NoSuchTagSet gracefully

        # Verify results
        assert "PublicAccessBlockConfiguration" in public_access_result
        assert "Name" in public_access_result
        assert "BucketEncryption" in encryption_result
        assert "Name" in encryption_result
        assert tagging_result == {
            "Name": "mixed-bucket",
            "Tags": [],
        }  # NoSuchTagSet handled gracefully
