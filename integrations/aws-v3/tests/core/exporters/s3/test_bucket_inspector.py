from typing import Any, Dict
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aws.core.exporters.s3.bucket.inspector import S3BucketInspector
from aws.core.exporters.s3.bucket.models import S3Bucket
from aws.core.interfaces.action import IAction

pytestmark = pytest.mark.asyncio


class MockAction(IAction):
    """Mock action for testing."""

    def __init__(self, client: AsyncMock, name: str = "MockAction") -> None:
        super().__init__(client)
        self.name = name

    async def _execute(self, identifier: str) -> Dict[str, Any]:
        return {"mock_data": f"data_for_{identifier}"}


class DummyAction(IAction):
    def __init__(self, client: MagicMock) -> None:
        self.client = client

    async def execute(self, bucket_name: str) -> dict[str, Any]:
        return {"dummy": f"{bucket_name}-data"}


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def inspector(mock_client: MagicMock) -> S3BucketInspector:
    return S3BucketInspector(mock_client)


@patch("aws.core.exporters.s3.bucket.inspector.S3BucketBuilder")
@patch("aws.core.exporters.s3.bucket.inspector.S3BucketActionsMap")
async def test_inspect_with_action_failure(
    mock_actions_map_cls: Any, mock_builder_cls: Any, inspector: "S3BucketInspector"
) -> None:
    dummy_bucket_name: str = "fail-bucket"
    dummy_include: list[str] = ["broken"]

    good_action: AsyncMock = AsyncMock(spec=IAction)
    good_action.execute.return_value = {"BucketName": "fail-bucket"}

    failing_action: AsyncMock = AsyncMock(spec=IAction)
    failing_action.execute.side_effect = Exception("Boom")

    mock_actions_map = mock_actions_map_cls.return_value
    mock_actions_map.merge.return_value = [
        lambda c: good_action,
        lambda c: failing_action,
    ]

    mock_builder: MagicMock = MagicMock()
    mock_builder_cls.return_value = mock_builder
    mock_builder.build.return_value = S3Bucket(
        Type="AWS::S3::Bucket", Properties=MagicMock()
    )

    result = await inspector.inspect(dummy_bucket_name, dummy_include)

    assert isinstance(result, S3Bucket)
    mock_builder.with_data.assert_called_once_with({"BucketName": "fail-bucket"})
    mock_builder.build.assert_called_once()


@patch("aws.core.exporters.s3.bucket.inspector.logger")
async def test_run_action_success(mock_logger: Any, inspector: Any) -> None:
    action: AsyncMock = AsyncMock(spec=IAction)
    action.__class__.__name__ = "DummyAction"
    action.execute.return_value = {"hello": "world"}

    result: dict[str, Any] = await inspector._run_action(action, "test-bucket")

    assert result == {"hello": "world"}
    mock_logger.info.assert_called_once()


@patch("aws.core.exporters.s3.bucket.inspector.logger")
async def test_run_action_failure(mock_logger: Any, inspector: Any) -> None:
    action: AsyncMock = AsyncMock(spec=IAction)
    action.__class__.__name__ = "FailingAction"
    action.execute.side_effect = Exception("Unexpected error")

    result: dict[str, Any] = await inspector._run_action(action, "test-bucket")

    assert result == {}
    mock_logger.warning.assert_called_once()
