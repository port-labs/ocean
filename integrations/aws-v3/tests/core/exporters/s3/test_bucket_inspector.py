from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.s3.bucket.inspector import S3BucketInspector
from aws.core.exporters.s3.bucket.models import S3Bucket, S3BucketProperties
from aws.core.interfaces.action import IAction


class MockAction(IAction):
    """Mock action for testing."""

    def __init__(self, client: AsyncMock, name: str = "MockAction") -> None:
        super().__init__(client)
        self.name = name

    async def _execute(self, identifier: str) -> Dict[str, Any]:
        return {"mock_data": f"data_for_{identifier}"}


class TestS3BucketInspector:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        return AsyncMock()

    @pytest.fixture
    def inspector(self, mock_client: AsyncMock) -> S3BucketInspector:
        """Create an S3BucketInspector instance for testing."""
        return S3BucketInspector(mock_client)

    def test_initialization(self, mock_client: AsyncMock) -> None:
        """Test that the inspector initializes with correct actions."""
        inspector = S3BucketInspector(mock_client)

        # Verify all expected actions are initialized
        action_names = [action.__class__.__name__ for action in inspector.actions]
        expected_actions = [
            "GetBucketPublicAccessBlockAction",
            "GetBucketOwnershipControlsAction",
            "GetBucketEncryptionAction",
            "GetBucketTaggingAction",
        ]

        assert len(inspector.actions) == 4
        for expected_action in expected_actions:
            assert expected_action in action_names

        # Verify all actions have the correct client
        for action in inspector.actions:
            assert action.client == mock_client

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.inspector.S3BucketBuilder")
    async def test_inspect_with_all_actions(
        self, mock_builder_class: MagicMock, inspector: S3BucketInspector
    ) -> None:
        """Test inspection with all actions included."""
        # Setup builder mock
        mock_builder = MagicMock()
        mock_bucket = S3Bucket(
            Identifier="test-bucket",
            Properties=S3BucketProperties(BucketName="test-bucket"),
        )
        mock_builder.build.return_value = mock_bucket
        mock_builder_class.return_value = mock_builder

        # Mock the _run_action method to return predictable results
        action_results: list[dict[str, Any]] = [
            {"PublicAccessBlockConfiguration": {"BlockPublicAcls": True}},
            {"OwnershipControls": {"Rules": []}},
            {"BucketEncryption": {"Rules": []}},
            {"Tags": [{"Key": "Environment", "Value": "test"}]},
        ]

        async def mock_run_action(action: Any, bucket_name: str) -> dict[str, Any]:
            action_name = action.__class__.__name__
            if action_name == "GetBucketPublicAccessBlockAction":
                return action_results[0]
            elif action_name == "GetBucketOwnershipControlsAction":
                return action_results[1]
            elif action_name == "GetBucketEncryptionAction":
                return action_results[2]
            elif action_name == "GetBucketTaggingAction":
                return action_results[3]
            return {}

        inspector._run_action = mock_run_action  # type: ignore

        # Include all actions
        include = [
            "GetBucketPublicAccessBlockAction",
            "GetBucketOwnershipControlsAction",
            "GetBucketEncryptionAction",
            "GetBucketTaggingAction",
        ]

        # Execute
        result = await inspector.inspect("test-bucket", include)

        # Verify
        assert result == mock_bucket
        mock_builder_class.assert_called_once_with("test-bucket")

        # Verify builder.with_data was called for each result
        assert mock_builder.with_data.call_count == 4
        for result_data in action_results:
            mock_builder.with_data.assert_any_call(result_data)

        mock_builder.build.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.inspector.S3BucketBuilder")
    async def test_inspect_with_subset_of_actions(
        self, mock_builder_class: MagicMock, inspector: S3BucketInspector
    ) -> None:
        """Test inspection with only subset of actions included."""
        # Setup builder mock
        mock_builder = MagicMock()
        mock_bucket = S3Bucket(Identifier="test-bucket")
        mock_builder.build.return_value = mock_bucket
        mock_builder_class.return_value = mock_builder

        # Mock the _run_action method to return predictable results
        async def mock_run_action(action: Any, bucket_name: str) -> dict[str, Any]:
            action_name = action.__class__.__name__
            if action_name == "GetBucketTaggingAction":
                return {"Tags": [{"Key": "Project", "Value": "demo"}]}
            elif action_name == "GetBucketEncryptionAction":
                return {"BucketEncryption": {"Rules": []}}
            return {}

        inspector._run_action = mock_run_action  # type: ignore

        # Include only 2 actions
        include = ["GetBucketTaggingAction", "GetBucketEncryptionAction"]

        # Execute
        result = await inspector.inspect("test-bucket", include)

        # Verify
        assert result == mock_bucket

        # Verify builder.with_data was called for each result
        assert mock_builder.with_data.call_count == 2
        mock_builder.build.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.inspector.S3BucketBuilder")
    async def test_inspect_with_no_actions(
        self, mock_builder_class: MagicMock, inspector: S3BucketInspector
    ) -> None:
        """Test inspection with no actions included."""
        # Setup builder mock
        mock_builder = MagicMock()
        mock_bucket = S3Bucket(Identifier="test-bucket")
        mock_builder.build.return_value = mock_bucket
        mock_builder_class.return_value = mock_builder

        # Include no actions
        include: List[str] = []

        # Execute
        result = await inspector.inspect("test-bucket", include)

        # Verify
        assert result == mock_bucket
        mock_builder_class.assert_called_once_with("test-bucket")

        # Verify builder.with_data was never called (no actions were included)
        assert mock_builder.with_data.call_count == 0
        mock_builder.build.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.inspector.S3BucketBuilder")
    async def test_inspect_with_none_results(
        self, mock_builder_class: MagicMock, inspector: S3BucketInspector
    ) -> None:
        """Test inspection handling None results from actions."""
        # Setup builder mock
        mock_builder = MagicMock()
        mock_bucket = S3Bucket(Identifier="test-bucket")
        mock_builder.build.return_value = mock_bucket
        mock_builder_class.return_value = mock_builder

        # Mock _run_action to simulate some actions failing (returning None)
        call_count = 0

        async def mock_run_action(
            action: Any, bucket_name: str
        ) -> dict[str, Any] | None:
            nonlocal call_count
            call_count += 1
            action_name = action.__class__.__name__
            if action_name == "GetBucketTaggingAction":
                return {"Tags": [{"Key": "Project", "Value": "demo"}]}
            elif action_name == "GetBucketPublicAccessBlockAction":
                return None  # Failed action
            elif action_name == "GetBucketEncryptionAction":
                return {"BucketEncryption": {"Rules": []}}
            elif action_name == "GetBucketOwnershipControlsAction":
                return None  # Another failed action
            return {}

        inspector._run_action = mock_run_action  # type: ignore

        # Include all actions
        include = [
            "GetBucketTaggingAction",
            "GetBucketPublicAccessBlockAction",
            "GetBucketEncryptionAction",
            "GetBucketOwnershipControlsAction",
        ]

        # Execute
        result = await inspector.inspect("test-bucket", include)

        # Verify
        assert result == mock_bucket

        # Verify builder.with_data was called only for non-None results
        assert mock_builder.with_data.call_count == 2
        mock_builder.with_data.assert_any_call(
            {"Tags": [{"Key": "Project", "Value": "demo"}]}
        )
        mock_builder.with_data.assert_any_call({"BucketEncryption": {"Rules": []}})

        mock_builder.build.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_action_success(self, inspector: S3BucketInspector) -> None:
        """Test successful action execution."""
        # Create a mock action
        mock_action = AsyncMock(spec=IAction)
        mock_action.__class__.__name__ = "TestAction"
        mock_action.execute.return_value = {"test_data": "success"}

        # Execute
        result = await inspector._run_action(mock_action, "test-bucket")

        # Verify
        assert result == {"test_data": "success"}
        mock_action.execute.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_run_action_exception(self, inspector: S3BucketInspector) -> None:
        """Test action execution with exception."""
        # Create a mock action that raises an exception
        mock_action = AsyncMock(spec=IAction)
        mock_action.__class__.__name__ = "FailingAction"
        mock_action.execute.side_effect = Exception("API error")

        # Execute
        result = await inspector._run_action(mock_action, "test-bucket")

        # Verify
        assert result == {}  # Should return empty dict on exception
        mock_action.execute.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.inspector.logger")
    async def test_run_action_logging(
        self, mock_logger: MagicMock, inspector: S3BucketInspector
    ) -> None:
        """Test that action execution is properly logged."""
        # Test successful action
        mock_action = AsyncMock(spec=IAction)
        mock_action.__class__.__name__ = "TestAction"
        mock_action.execute.return_value = {"test_data": "success"}

        await inspector._run_action(mock_action, "test-bucket")

        # Verify info log for successful action
        mock_logger.info.assert_called_with(
            "Running action TestAction for bucket test-bucket"
        )

        # Reset logger mock
        mock_logger.reset_mock()

        # Test failing action
        mock_action.execute.side_effect = Exception("API error")

        await inspector._run_action(mock_action, "test-bucket")

        # Verify warning log for failed action
        mock_logger.info.assert_called_with(
            "Running action TestAction for bucket test-bucket"
        )
        mock_logger.warning.assert_called_with("TestAction failed: API error")

    @pytest.mark.asyncio
    async def test_inspect_integration(self, mock_client: AsyncMock) -> None:
        """Test inspector integration with real-like action behavior."""
        # Create inspector with mock actions that return valid S3 properties
        inspector = S3BucketInspector(mock_client)

        # Replace actions with mock versions for predictable testing
        mock_actions = []
        action_configs = [
            (
                "GetBucketTaggingAction",
                {"Tags": [{"Key": "TestKey0", "Value": "TestValue0"}]},
            ),
            ("GetBucketEncryptionAction", {"BucketEncryption": {"Rules": []}}),
            (
                "GetBucketPublicAccessBlockAction",
                {"PublicAccessBlockConfiguration": {"BlockPublicAcls": True}},
            ),
        ]

        for action_name, return_value in action_configs:
            mock_action = AsyncMock(spec=IAction)
            # Create a mock class with the proper name
            mock_class = type(action_name, (), {})
            mock_action.__class__ = mock_class
            mock_action.execute.return_value = return_value
            mock_actions.append(mock_action)

        inspector.actions = mock_actions  # type: ignore

        # Execute with subset of actions
        include = ["GetBucketTaggingAction", "GetBucketPublicAccessBlockAction"]
        result = await inspector.inspect("integration-bucket", include)

        # Verify result structure
        assert isinstance(result, S3Bucket)
        assert result.Identifier == "integration-bucket"
        assert result.Type == "AWS::S3::Bucket"

        # Verify only included actions were executed
        mock_actions[0].execute.assert_called_once_with(
            "integration-bucket"
        )  # GetBucketTaggingAction
        mock_actions[
            1
        ].execute.assert_not_called()  # GetBucketEncryptionAction - not included
        mock_actions[2].execute.assert_called_once_with(
            "integration-bucket"
        )  # GetBucketPublicAccessBlockAction

        # Verify data was added to bucket properties
        properties_dict = result.Properties.dict(exclude_none=True)
        assert "Tags" in properties_dict
        assert properties_dict["Tags"] == [{"Key": "TestKey0", "Value": "TestValue0"}]
        assert "PublicAccessBlockConfiguration" in properties_dict
        assert properties_dict["PublicAccessBlockConfiguration"] == {
            "BlockPublicAcls": True
        }
        assert (
            "BucketEncryption" not in properties_dict
        )  # GetBucketEncryptionAction was not included
