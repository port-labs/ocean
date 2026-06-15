import pytest
from pydantic import ValidationError

from aws.core.exporters.codepipeline.action.models import (
    ActionTypeIdProperties,
    CodePipelineActionProperties,
    CodePipelineAction,
    SingleCodePipelineActionRequest,
    PaginatedCodePipelineActionRequest,
)


class TestActionTypeIdProperties:

    def test_valid_action_type_id(self) -> None:
        """Test creation of valid ActionTypeIdProperties."""
        action_type = ActionTypeIdProperties(
            Category="Source", Owner="AWS", Provider="S3", Version="1"
        )

        assert action_type.Category == "Source"
        assert action_type.Owner == "AWS"
        assert action_type.Provider == "S3"
        assert action_type.Version == "1"

    def test_default_values(self) -> None:
        """Test default factory values."""
        action_type = ActionTypeIdProperties()

        assert action_type.Category == ""
        assert action_type.Owner == ""
        assert action_type.Provider == ""
        assert action_type.Version == ""

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            ActionTypeIdProperties(
                Category="Source",
                Owner="AWS",
                Provider="S3",
                Version="1",
                ExtraField="not_allowed",
            )


class TestCodePipelineActionProperties:

    def test_valid_action_properties(self) -> None:
        """Test creation of valid CodePipelineActionProperties."""
        action_props = CodePipelineActionProperties(
            ActionName="SourceAction",
            ActionTypeId=ActionTypeIdProperties(
                Category="Source", Owner="AWS", Provider="S3", Version="1"
            ),
            RunOrder=1,
            Configuration={"S3Bucket": "test-bucket"},
            PipelineName="test-pipeline",
            StageName="Source",
        )

        assert action_props.ActionName == "SourceAction"
        assert action_props.ActionTypeId.Category == "Source"
        assert action_props.RunOrder == 1
        assert action_props.Configuration == {"S3Bucket": "test-bucket"}
        assert action_props.PipelineName == "test-pipeline"
        assert action_props.StageName == "Source"

    def test_default_values(self) -> None:
        """Test default factory values."""
        action_props = CodePipelineActionProperties()

        assert action_props.ActionName == ""
        assert action_props.ActionTypeId is None
        assert action_props.RunOrder is None
        assert action_props.Configuration is None
        assert action_props.InputArtifacts == []
        assert action_props.OutputArtifacts == []
        assert action_props.PipelineName == ""
        assert action_props.StageName == ""

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            CodePipelineActionProperties(
                ActionName="TestAction", ExtraField="not_allowed"
            )


class TestCodePipelineAction:

    def test_valid_action(self) -> None:
        """Test creation of valid CodePipelineAction."""
        action = CodePipelineAction(
            Properties=CodePipelineActionProperties(
                ActionName="SourceAction",
                PipelineName="test-pipeline",
                StageName="Source",
            )
        )

        assert action.Type == "AWS::CodePipeline::Action"
        assert action.Properties.ActionName == "SourceAction"
        assert action.Properties.PipelineName == "test-pipeline"
        assert action.Properties.StageName == "Source"

    def test_default_properties(self) -> None:
        """Test default properties factory."""
        action = CodePipelineAction()

        assert action.Type == "AWS::CodePipeline::Action"
        assert isinstance(action.Properties, CodePipelineActionProperties)
        assert action.Properties.ActionName == ""


class TestSingleCodePipelineActionRequest:

    def test_valid_request(self) -> None:
        """Test creation of valid SingleCodePipelineActionRequest."""
        request = SingleCodePipelineActionRequest(
            pipeline_name="test-pipeline",
            stage_name="Source",
            action_name="SourceAction",
            region="us-east-1",
            account_id="123456789012",
        )

        assert request.pipeline_name == "test-pipeline"
        assert request.stage_name == "Source"
        assert request.action_name == "SourceAction"
        assert request.region == "us-east-1"
        assert request.account_id == "123456789012"

    def test_missing_required_fields(self) -> None:
        """Test validation error with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            SingleCodePipelineActionRequest()

        errors = exc_info.value.errors()
        required_fields = {
            error["loc"][0] for error in errors if error["type"] == "missing"
        }

        assert "pipeline_name" in required_fields
        assert "stage_name" in required_fields
        assert "action_name" in required_fields


class TestPaginatedCodePipelineActionRequest:

    def test_valid_request(self) -> None:
        """Test creation of valid PaginatedCodePipelineActionRequest."""
        request = PaginatedCodePipelineActionRequest(
            region="us-east-1", account_id="123456789012"
        )

        assert request.region == "us-east-1"
        assert request.account_id == "123456789012"

    def test_default_request(self) -> None:
        """Test creation with minimal required fields."""
        request = PaginatedCodePipelineActionRequest()

        # Should not raise validation error as this inherits from ResourceRequestModel
        # which may have optional base fields
        assert isinstance(request, PaginatedCodePipelineActionRequest)
