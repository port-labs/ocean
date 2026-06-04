from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.codepipeline.pipeline.actions import (
    GetPipelineDetailsAction,
    GetPipelineTagsAction,
    ListPipelinesAction,
    PipelineActionsMap,
)
from aws.core.interfaces.action import Action


class _PipelineNotFoundException(Exception):
    pass


class _ResourceNotFoundException(Exception):
    pass


def _make_exceptions_mock() -> MagicMock:
    """Build a mock that exposes the CodePipeline exception classes used by actions."""
    exceptions = MagicMock()
    exceptions.PipelineNotFoundException = _PipelineNotFoundException
    exceptions.ResourceNotFoundException = _ResourceNotFoundException
    return exceptions


class TestGetPipelineDetailsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.get_pipeline = AsyncMock()
        mock_client.exceptions = _make_exceptions_mock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetPipelineDetailsAction:
        """Create a GetPipelineDetailsAction instance for testing."""
        return GetPipelineDetailsAction(mock_client)

    def test_inheritance(self, action: GetPipelineDetailsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetPipelineDetailsAction) -> None:
        """Test successful execution of get_pipeline for multiple pipelines."""
        pipelines = [{"name": "pipeline-1"}, {"name": "pipeline-2"}]

        created_dt = datetime(2023, 12, 1, 10, 30, 0)
        updated_dt = datetime(2023, 12, 2, 10, 30, 0)

        def mock_get_pipeline(name: str, **kwargs: Any) -> dict[str, Any]:
            return {
                "pipeline": {
                    "name": name,
                    "roleArn": f"arn:aws:iam::123456789012:role/{name}-role",
                    "artifactStore": {
                        "location": f"{name}-bucket",
                        "type": "S3",
                        "encryptionKey": None,
                    },
                    "artifactStores": {},
                    "stages": [
                        {
                            "name": "Source",
                            "actions": [{"name": "SourceAction"}],
                            "blockers": [],
                        }
                    ],
                    "version": 1,
                    "executionMode": "QUEUED",
                    "pipelineType": "V2",
                    "variables": [],
                    "triggers": [],
                },
                "metadata": {
                    "pipelineArn": f"arn:aws:codepipeline:us-east-1:123456789012:{name}",
                    "created": created_dt,
                    "updated": updated_dt,
                },
            }

        action.client.get_pipeline.side_effect = mock_get_pipeline

        result = await action.execute(pipelines)

        assert len(result) == 2
        assert result[0]["Name"] == "pipeline-1"
        assert (
            result[0]["Arn"] == "arn:aws:codepipeline:us-east-1:123456789012:pipeline-1"
        )
        assert result[0]["RoleArn"] == "arn:aws:iam::123456789012:role/pipeline-1-role"
        assert result[0]["ArtifactStore"]["location"] == "pipeline-1-bucket"
        assert result[0]["ArtifactStore"]["type"] == "S3"
        assert result[0]["ArtifactStores"] == {}
        assert result[0]["Stages"][0]["name"] == "Source"
        assert result[0]["Version"] == 1
        assert result[0]["ExecutionMode"] == "QUEUED"
        assert result[0]["PipelineType"] == "V2"
        assert result[0]["Created"] == created_dt.isoformat()
        assert result[0]["Updated"] == updated_dt.isoformat()
        assert result[1]["Name"] == "pipeline-2"

        assert action.client.get_pipeline.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: GetPipelineDetailsAction) -> None:
        """Test execution with empty pipeline list."""
        pipelines: list[dict[str, Any]] = []

        result = await action.execute(pipelines)

        assert result == []
        action.client.get_pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_single_pipeline(
        self, action: GetPipelineDetailsAction
    ) -> None:
        """Test execution with a single pipeline."""
        pipelines = [{"name": "single-pipeline"}]

        action.client.get_pipeline.return_value = {
            "pipeline": {
                "name": "single-pipeline",
                "roleArn": "arn:aws:iam::123456789012:role/single-pipeline-role",
                "artifactStore": {"location": "bucket", "type": "S3"},
                "artifactStores": {},
                "stages": [],
                "version": 1,
                "executionMode": "QUEUED",
                "pipelineType": "V2",
                "variables": [],
                "triggers": [],
            },
            "metadata": {
                "pipelineArn": "arn:aws:codepipeline:us-east-1:123456789012:single-pipeline",
                "created": None,
                "updated": None,
            },
        }

        result = await action.execute(pipelines)

        assert len(result) == 1
        assert result[0]["Name"] == "single-pipeline"
        assert result[0]["Created"] is None
        assert result[0]["Updated"] is None
        action.client.get_pipeline.assert_called_once_with(name="single-pipeline")

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_with_pipeline_not_found(
        self, mock_logger: MagicMock, action: GetPipelineDetailsAction
    ) -> None:
        """Test that PipelineNotFoundException is handled gracefully (returns empty dict)."""
        pipelines = [{"name": "missing-pipeline"}]

        action.client.get_pipeline.side_effect = _PipelineNotFoundException(
            "pipeline not found"
        )

        result = await action.execute(pipelines)

        # PipelineNotFoundException returns {} which still gets appended to results
        assert result == [{}]
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "missing-pipeline" in warning_call

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_with_unrecoverable_exception(
        self, mock_logger: MagicMock, action: GetPipelineDetailsAction
    ) -> None:
        """Test that non-recoverable exceptions are logged and the pipeline is skipped."""
        pipelines = [
            {"name": "pipeline-1"},
            {"name": "pipeline-2"},
        ]

        created_dt = datetime(2023, 12, 1, 10, 30, 0)

        def mock_get_pipeline(name: str, **kwargs: Any) -> dict[str, Any]:
            if name == "pipeline-1":
                return {
                    "pipeline": {
                        "name": "pipeline-1",
                        "roleArn": "arn:aws:iam::123456789012:role/pipeline-1-role",
                        "artifactStore": {"location": "bucket", "type": "S3"},
                        "artifactStores": {},
                        "stages": [],
                        "version": 1,
                        "executionMode": "QUEUED",
                        "pipelineType": "V2",
                        "variables": [],
                        "triggers": [],
                    },
                    "metadata": {
                        "pipelineArn": "arn:aws:codepipeline:us-east-1:123456789012:pipeline-1",
                        "created": created_dt,
                        "updated": created_dt,
                    },
                }
            raise RuntimeError("Boom")

        action.client.get_pipeline.side_effect = mock_get_pipeline

        result = await action.execute(pipelines)

        # The failing pipeline is skipped, only the successful one is returned
        assert len(result) == 1
        assert result[0]["Name"] == "pipeline-1"

        # Verify error logging mentions the failing pipeline
        mock_logger.error.assert_called()
        error_calls = [call.args[0] for call in mock_logger.error.call_args_list]
        assert any("pipeline-2" in c for c in error_calls)


class TestGetPipelineTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.get_pipeline = AsyncMock()
        mock_client.list_tags_for_resource = AsyncMock()
        mock_client.exceptions = _make_exceptions_mock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetPipelineTagsAction:
        """Create a GetPipelineTagsAction instance for testing."""
        return GetPipelineTagsAction(mock_client)

    def test_inheritance(self, action: GetPipelineTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test successful execution of list_tags_for_resource."""
        pipelines = [
            {"name": "pipeline-1"},
            {"name": "pipeline-2"},
        ]

        def mock_get_pipeline(name: str, **kwargs: Any) -> dict[str, Any]:
            return {
                "metadata": {
                    "pipelineArn": f"arn:aws:codepipeline:us-east-1:123456789012:{name}",
                }
            }

        def mock_list_tags_for_resource(
            resourceArn: str, **kwargs: Any
        ) -> dict[str, Any]:
            if resourceArn.endswith("pipeline-1"):
                return {
                    "tags": [
                        {"key": "Environment", "value": "production"},
                        {"key": "Project", "value": "web-app"},
                    ]
                }
            elif resourceArn.endswith("pipeline-2"):
                return {
                    "tags": [
                        {"key": "Environment", "value": "staging"},
                        {"key": "Owner", "value": "devops-team"},
                    ]
                }
            return {"tags": []}

        action.client.get_pipeline.side_effect = mock_get_pipeline
        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(pipelines)

        expected_result = [
            {"Tags": {"Environment": "production", "Project": "web-app"}},
            {"Tags": {"Environment": "staging", "Owner": "devops-team"}},
        ]
        assert result == expected_result

        assert action.client.get_pipeline.call_count == 2
        assert action.client.list_tags_for_resource.call_count == 2
        action.client.list_tags_for_resource.assert_any_call(
            resourceArn="arn:aws:codepipeline:us-east-1:123456789012:pipeline-1"
        )
        action.client.list_tags_for_resource.assert_any_call(
            resourceArn="arn:aws:codepipeline:us-east-1:123456789012:pipeline-2"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_with_pipeline_not_found(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test that PipelineNotFoundException returns empty tags and logs a warning."""
        pipelines = [
            {"name": "pipeline-1"},
            {"name": "missing-pipeline"},
        ]

        def mock_get_pipeline(name: str, **kwargs: Any) -> dict[str, Any]:
            if name == "pipeline-1":
                return {
                    "metadata": {
                        "pipelineArn": "arn:aws:codepipeline:us-east-1:123456789012:pipeline-1",
                    }
                }
            raise _PipelineNotFoundException("not found")

        action.client.get_pipeline.side_effect = mock_get_pipeline
        action.client.list_tags_for_resource.return_value = {
            "tags": [{"key": "Environment", "value": "production"}]
        }

        result = await action.execute(pipelines)

        expected_result = [
            {"Tags": {"Environment": "production"}},
            {"Tags": {}},
        ]
        assert result == expected_result

        mock_logger.warning.assert_called()
        warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("missing-pipeline" in c for c in warning_calls)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_with_resource_not_found(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test that ResourceNotFoundException returns empty tags."""
        pipelines = [{"name": "pipeline-1"}]

        action.client.get_pipeline.return_value = {
            "metadata": {
                "pipelineArn": "arn:aws:codepipeline:us-east-1:123456789012:pipeline-1",
            }
        }
        action.client.list_tags_for_resource.side_effect = _ResourceNotFoundException(
            "no tags"
        )

        result = await action.execute(pipelines)

        assert result == [{"Tags": {}}]
        mock_logger.warning.assert_called()
        warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("pipeline-1" in c for c in warning_calls)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_with_generic_exception_returns_empty_tags(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test that a generic exception is caught and returns empty tags."""
        pipelines = [{"name": "pipeline-1"}]

        action.client.get_pipeline.side_effect = RuntimeError("Boom")

        result = await action.execute(pipelines)

        # _fetch_pipeline_tags catches the generic Exception and returns {"Tags": {}}
        assert result == [{"Tags": {}}]
        mock_logger.error.assert_called()
        error_calls = [call.args[0] for call in mock_logger.error.call_args_list]
        assert any("pipeline-1" in c for c in error_calls)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_missing_arn_returns_empty_tags(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test that a missing pipeline ARN results in empty tags."""
        pipelines = [{"name": "pipeline-1"}]

        action.client.get_pipeline.return_value = {"metadata": {}}

        result = await action.execute(pipelines)

        assert result == [{"Tags": {}}]
        action.client.list_tags_for_resource.assert_not_called()
        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_empty_pipeline_list(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test execution with empty pipeline list."""
        result = await action.execute([])

        assert result == []
        action.client.get_pipeline.assert_not_called()
        action.client.list_tags_for_resource.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.actions.logger")
    async def test_execute_empty_tag_list(
        self, mock_logger: MagicMock, action: GetPipelineTagsAction
    ) -> None:
        """Test execution when pipeline has no tags."""
        pipelines = [{"name": "pipeline-1"}]

        action.client.get_pipeline.return_value = {
            "metadata": {
                "pipelineArn": "arn:aws:codepipeline:us-east-1:123456789012:pipeline-1",
            }
        }
        action.client.list_tags_for_resource.return_value = {"tags": []}

        result = await action.execute(pipelines)

        assert result == [{"Tags": {}}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:codepipeline:us-east-1:123456789012:pipeline-1"
        )


class TestListPipelinesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListPipelinesAction:
        """Create a ListPipelinesAction instance for testing."""
        return ListPipelinesAction(mock_client)

    def test_inheritance(self, action: ListPipelinesAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListPipelinesAction) -> None:
        """Test successful execution of list_pipelines transformation."""
        created_dt = datetime(2023, 12, 1, 10, 30, 0)
        updated_dt = datetime(2023, 12, 2, 10, 30, 0)
        pipelines = [
            {
                "name": "pipeline-1",
                "version": 1,
                "created": created_dt,
                "updated": updated_dt,
            },
            {
                "name": "pipeline-2",
                "version": 2,
                "created": created_dt,
                "updated": updated_dt,
            },
        ]

        result = await action.execute(pipelines)

        assert result == [
            {
                "name": "pipeline-1",
                "version": 1,
                "created": created_dt.isoformat(),
                "updated": updated_dt.isoformat(),
            },
            {
                "name": "pipeline-2",
                "version": 2,
                "created": created_dt.isoformat(),
                "updated": updated_dt.isoformat(),
            },
        ]
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListPipelinesAction) -> None:
        """Test execution with empty pipeline list."""
        pipelines: list[dict[str, Any]] = []

        result = await action.execute(pipelines)

        assert result == []
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_execute_single_pipeline(self, action: ListPipelinesAction) -> None:
        """Test execution with a single pipeline."""
        created_dt = datetime(2023, 12, 1, 12, 0, 0)
        pipelines = [
            {
                "name": "single-pipeline",
                "version": 3,
                "created": created_dt,
                "updated": created_dt,
            }
        ]

        result = await action.execute(pipelines)

        assert len(result) == 1
        assert result[0]["name"] == "single-pipeline"
        assert result[0]["version"] == 3
        assert result[0]["created"] == created_dt.isoformat()

    @pytest.mark.asyncio
    async def test_execute_missing_timestamps(
        self, action: ListPipelinesAction
    ) -> None:
        """Test that missing timestamps are emitted as None."""
        pipelines = [{"name": "pipeline-1", "version": 1}]

        result = await action.execute(pipelines)

        assert result == [
            {
                "name": "pipeline-1",
                "version": 1,
                "created": None,
                "updated": None,
            }
        ]


class TestPipelineActionsMap:

    def test_merge_includes_defaults(self) -> None:
        """Test that merge includes all default actions."""
        action_map = PipelineActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert "GetPipelineDetailsAction" in names
        assert "GetPipelineTagsAction" in names
        assert "ListPipelinesAction" in names

    def test_merge_with_empty_options(self) -> None:
        """Test that merge works with empty options list and yields just the defaults."""
        action_map = PipelineActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert names == [
            "GetPipelineDetailsAction",
            "GetPipelineTagsAction",
            "ListPipelinesAction",
        ]
        assert len(names) == 3

    def test_merge_with_options(self) -> None:
        """Test that merge still returns defaults when include lists action names."""
        # PipelineActionsMap has no optional actions, but include should be tolerated
        include = ["GetPipelineTagsAction"]
        actions = PipelineActionsMap().merge(include)
        names = [a.__name__ for a in actions]
        assert "GetPipelineDetailsAction" in names
        assert "GetPipelineTagsAction" in names
        assert "ListPipelinesAction" in names

    def test_merge_with_nonexistent_options(self) -> None:
        """Test that merge handles nonexistent option actions gracefully."""
        action_map = PipelineActionsMap()
        merged = action_map.merge(["NonExistentAction"])

        # Should still include all defaults
        names = [cls.__name__ for cls in merged]
        assert "GetPipelineDetailsAction" in names
        assert "GetPipelineTagsAction" in names
        assert "ListPipelinesAction" in names

    def test_options_is_empty(self) -> None:
        """Test that there are no optional actions for the pipeline kind."""
        action_map = PipelineActionsMap()
        assert action_map.options == []
