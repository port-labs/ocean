from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.codepipeline.action.actions import (
    GetPipelineDetailsAction,
    ListPipelinesAction,
    GetPipelineExecutionDetailsAction,
    CodePipelineActionActionsMap,
)
from aws.core.interfaces.action import Action


class TestGetPipelineDetailsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock CodePipeline client for testing."""
        mock_client = AsyncMock()
        mock_client.get_pipeline = AsyncMock()
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
        """Test successful execution of get_pipeline_details."""
        # Mock response
        expected_response = {
            "pipeline": {
                "name": "test-pipeline",
                "roleArn": "arn:aws:iam::123456789012:role/service-role/codepipeline-test-role",
                "version": 1,
                "stages": [
                    {
                        "name": "Source",
                        "actions": [
                            {
                                "name": "SourceAction",
                                "actionTypeId": {
                                    "category": "Source",
                                    "owner": "AWS",
                                    "provider": "S3",
                                    "version": "1",
                                },
                                "runOrder": 1,
                                "configuration": {
                                    "S3Bucket": "test-bucket",
                                    "S3ObjectKey": "source.zip",
                                },
                                "outputArtifacts": [{"name": "SourceOutput"}],
                            }
                        ],
                    },
                    {
                        "name": "Build",
                        "actions": [
                            {
                                "name": "BuildAction",
                                "actionTypeId": {
                                    "category": "Build",
                                    "owner": "AWS",
                                    "provider": "CodeBuild",
                                    "version": "1",
                                },
                                "runOrder": 1,
                                "configuration": {"ProjectName": "test-project"},
                                "inputArtifacts": [{"name": "SourceOutput"}],
                                "outputArtifacts": [{"name": "BuildOutput"}],
                            }
                        ],
                    },
                ],
            }
        }

        action.client.get_pipeline.return_value = expected_response

        # Execute the action
        result = await action._execute(["test-pipeline"])

        # Verify the results
        assert len(result) == 2  # Should have 2 actions extracted

        # Check first action (Source)
        source_action = result[0]
        assert source_action["ActionName"] == "SourceAction"
        assert source_action["PipelineName"] == "test-pipeline"
        assert source_action["StageName"] == "Source"
        assert source_action["ActionTypeId"]["Category"] == "Source"
        assert source_action["ActionTypeId"]["Provider"] == "S3"

        # Check second action (Build)
        build_action = result[1]
        assert build_action["ActionName"] == "BuildAction"
        assert build_action["PipelineName"] == "test-pipeline"
        assert build_action["StageName"] == "Build"
        assert build_action["ActionTypeId"]["Category"] == "Build"
        assert build_action["ActionTypeId"]["Provider"] == "CodeBuild"

        # Verify client was called correctly
        action.client.get_pipeline.assert_called_once_with(name="test-pipeline")

    @pytest.mark.asyncio
    async def test_execute_empty_pipeline_list(
        self, action: GetPipelineDetailsAction
    ) -> None:
        """Test execution with empty pipeline list."""
        result = await action._execute([])
        assert result == []
        action.client.get_pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_client_error(self, action: GetPipelineDetailsAction) -> None:
        """Test execution with client error."""
        action.client.get_pipeline.side_effect = ClientError(
            error_response={
                "Error": {"Code": "PipelineNotFound", "Message": "Pipeline not found"}
            },
            operation_name="GetPipeline",
        )

        with pytest.raises(ClientError):
            await action._execute(["nonexistent-pipeline"])


class TestListPipelinesAction:

    @pytest.fixture
    def action(self) -> ListPipelinesAction:
        """Create a ListPipelinesAction instance for testing."""
        return ListPipelinesAction(None)

    def test_inheritance(self, action: ListPipelinesAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListPipelinesAction) -> None:
        """Test successful execution of list_pipelines."""
        pipeline_list = [
            {"name": "pipeline-1", "version": 1},
            {"name": "pipeline-2", "version": 2},
            "pipeline-3",  # Test string format too
        ]

        result = await action._execute(pipeline_list)

        expected = ["pipeline-1", "pipeline-2", "pipeline-3"]
        assert result == expected

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListPipelinesAction) -> None:
        """Test execution with empty list."""
        result = await action._execute([])
        assert result == []


class TestCodePipelineActionActionsMap:

    def test_defaults(self) -> None:
        """Test that defaults contain expected actions."""
        actions_map = CodePipelineActionActionsMap()
        default_action_types = [type(action) for action in actions_map.defaults]

        assert ListPipelinesAction in default_action_types
        assert GetPipelineDetailsAction in default_action_types

    def test_options(self) -> None:
        """Test that options contain expected actions."""
        actions_map = CodePipelineActionActionsMap()
        option_action_types = [type(action) for action in actions_map.options]

        assert GetPipelineExecutionDetailsAction in option_action_types
