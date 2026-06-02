import pytest
from pydantic import ValidationError

from aws.core.exporters.codepipeline.pipeline.models import (
    Pipeline,
    PipelineProperties,
    PipelineArtifactStore,
    PipelineStage,
    SinglePipelineRequest,
    PaginatedPipelineRequest,
)


class TestSinglePipelineRequest:

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = SinglePipelineRequest(
            region="us-west-2", account_id="123456789012", pipeline_name="test-pipeline"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.pipeline_name == "test-pipeline"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["ListPipelinesAction"]
        options = SinglePipelineRequest(
            region="eu-central-1",
            account_id="123456789012",
            pipeline_name="test-pipeline",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.pipeline_name == "test-pipeline"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test validation error when region is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SinglePipelineRequest(
                account_id="123456789012", pipeline_name="test-pipeline"
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_pipeline_name(self) -> None:
        """Test validation error when pipeline_name is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SinglePipelineRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "pipeline_name" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test initialization with empty include list."""
        options = SinglePipelineRequest(
            region="us-east-1",
            account_id="123456789012",
            pipeline_name="test-pipeline",
            include=[],
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        """Test include list with multiple actions."""
        options = SinglePipelineRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            pipeline_name="test-pipeline",
            include=["ListPipelinesAction", "GetPipelineAction"],
        )
        assert len(options.include) == 2
        assert "ListPipelinesAction" in options.include
        assert "GetPipelineAction" in options.include


class TestPaginatedPipelineRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedPipelineRequest inherits properly."""
        options = PaginatedPipelineRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedPipelineRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = PaginatedPipelineRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include actions."""
        include_list = ["ListPipelinesAction"]
        options = PaginatedPipelineRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )
        assert options.region == "ap-southeast-2"
        assert options.account_id == "123456789012"
        assert options.include == include_list


class TestPipelineArtifactStore:

    def test_initialization_empty(self) -> None:
        """Test initialization with default values."""
        store = PipelineArtifactStore()
        assert store.location is None
        assert store.type is None
        assert store.encryptionKey is None

    def test_initialization_with_values(self) -> None:
        """Test initialization with specific values."""
        store = PipelineArtifactStore(
            location="my-bucket",
            type="S3",
            encryptionKey={"id": "alias/aws/s3", "type": "KMS"},
        )
        assert store.location == "my-bucket"
        assert store.type == "S3"
        assert store.encryptionKey == {"id": "alias/aws/s3", "type": "KMS"}

    def test_extra_fields_are_ignored(self) -> None:
        """Test that extra fields are ignored."""
        store = PipelineArtifactStore(
            location="my-bucket",
            type="S3",
            unknownField="should-be-ignored",  # type: ignore
        )
        assert store.location == "my-bucket"
        assert not hasattr(store, "unknownField")


class TestPipelineStage:

    def test_initialization_empty(self) -> None:
        """Test initialization with default values."""
        stage = PipelineStage()
        assert stage.name is None
        assert stage.actions == []
        assert stage.blockers == []

    def test_initialization_with_values(self) -> None:
        """Test initialization with specific values."""
        actions = [{"name": "SourceAction", "actionTypeId": {"category": "Source"}}]
        blockers = [{"name": "ManualApproval", "type": "Schedule"}]
        stage = PipelineStage(name="Source", actions=actions, blockers=blockers)
        assert stage.name == "Source"
        assert stage.actions == actions
        assert stage.blockers == blockers

    def test_extra_fields_are_ignored(self) -> None:
        """Test that extra fields are ignored."""
        stage = PipelineStage(name="Source", unknownField="ignored")  # type: ignore
        assert stage.name == "Source"
        assert not hasattr(stage, "unknownField")


class TestPipelineProperties:

    def test_initialization_empty(self) -> None:
        """Test initialization with default values."""
        properties = PipelineProperties()
        assert properties.Name == ""
        assert properties.Arn is None
        assert properties.RoleArn is None
        assert properties.ArtifactStore is None
        assert properties.ArtifactStores == {}
        assert properties.Stages == []
        assert properties.Version is None
        assert properties.ExecutionMode is None
        assert properties.PipelineType is None
        assert properties.Variables == []
        assert properties.Triggers == []
        assert properties.Created is None
        assert properties.Updated is None
        assert properties.Tags == {}

    def test_initialization_with_properties(self) -> None:
        """Test initialization with specific properties."""
        properties = PipelineProperties(
            Name="test-pipeline",
            Arn="arn:aws:codepipeline:us-east-1:123456789012:test-pipeline",
            RoleArn="arn:aws:iam::123456789012:role/codepipeline-role",
            Version=1,
            ExecutionMode="QUEUED",
            PipelineType="V2",
            Created="2023-12-01T10:30:00.000+0000",
            Updated="2023-12-02T10:30:00.000+0000",
            Tags={"Environment": "test"},
        )
        assert properties.Name == "test-pipeline"
        assert (
            properties.Arn
            == "arn:aws:codepipeline:us-east-1:123456789012:test-pipeline"
        )
        assert properties.RoleArn == "arn:aws:iam::123456789012:role/codepipeline-role"
        assert properties.Version == 1
        assert properties.ExecutionMode == "QUEUED"
        assert properties.PipelineType == "V2"
        assert properties.Created == "2023-12-01T10:30:00.000+0000"
        assert properties.Updated == "2023-12-02T10:30:00.000+0000"
        assert properties.Tags == {"Environment": "test"}

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        properties = PipelineProperties(
            Name="test-pipeline",
            PipelineType="V2",
            Tags={"Project": "demo"},
        )
        result = properties.dict(exclude_none=True)
        assert result["Name"] == "test-pipeline"
        assert result["PipelineType"] == "V2"
        assert result["Tags"] == {"Project": "demo"}
        # Arn is excluded because it's None
        assert "Arn" not in result
        assert "RoleArn" not in result

    def test_artifact_store_nested_model(self) -> None:
        """Test that ArtifactStore accepts a nested model."""
        store = PipelineArtifactStore(location="my-bucket", type="S3")
        properties = PipelineProperties(Name="test-pipeline", ArtifactStore=store)
        assert properties.ArtifactStore is not None
        assert properties.ArtifactStore.location == "my-bucket"
        assert properties.ArtifactStore.type == "S3"

    def test_artifact_stores_dict_of_models(self) -> None:
        """Test that ArtifactStores accepts a dict of nested models."""
        properties = PipelineProperties(
            Name="test-pipeline",
            ArtifactStores={
                "us-east-1": PipelineArtifactStore(location="bucket-east", type="S3"),
                "us-west-2": PipelineArtifactStore(location="bucket-west", type="S3"),
            },
        )
        assert len(properties.ArtifactStores) == 2
        assert properties.ArtifactStores["us-east-1"].location == "bucket-east"
        assert properties.ArtifactStores["us-west-2"].location == "bucket-west"

    def test_stages_list_of_models(self) -> None:
        """Test that Stages accepts a list of nested models."""
        properties = PipelineProperties(
            Name="test-pipeline",
            Stages=[
                PipelineStage(name="Source", actions=[{"name": "SourceAction"}]),
                PipelineStage(name="Deploy", actions=[{"name": "DeployAction"}]),
            ],
        )
        assert len(properties.Stages) == 2
        assert properties.Stages[0].name == "Source"
        assert properties.Stages[1].name == "Deploy"

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        properties = PipelineProperties(
            Name="comprehensive-pipeline",
            Arn="arn:aws:codepipeline:us-east-1:123456789012:comprehensive-pipeline",
            RoleArn="arn:aws:iam::123456789012:role/codepipeline-role",
            ArtifactStore=PipelineArtifactStore(location="artifact-bucket", type="S3"),
            ArtifactStores={
                "us-east-1": PipelineArtifactStore(
                    location="artifact-bucket-east", type="S3"
                )
            },
            Stages=[
                PipelineStage(
                    name="Source",
                    actions=[
                        {
                            "name": "SourceAction",
                            "actionTypeId": {
                                "category": "Source",
                                "owner": "AWS",
                                "provider": "CodeStarSourceConnection",
                                "version": "1",
                            },
                        }
                    ],
                ),
                PipelineStage(
                    name="Build",
                    actions=[
                        {
                            "name": "BuildAction",
                            "actionTypeId": {
                                "category": "Build",
                                "owner": "AWS",
                                "provider": "CodeBuild",
                                "version": "1",
                            },
                        }
                    ],
                ),
            ],
            Version=2,
            ExecutionMode="PARALLEL",
            PipelineType="V2",
            Variables=[{"name": "ENV", "defaultValue": "prod"}],
            Triggers=[{"providerType": "CodeStarSourceConnection"}],
            Created="2023-12-01T10:30:00.000+0000",
            Updated="2023-12-02T10:30:00.000+0000",
            Tags={"Name": "comprehensive-pipeline", "Environment": "production"},
        )

        # Verify key properties
        assert properties.Name == "comprehensive-pipeline"
        assert properties.PipelineType == "V2"
        assert properties.Version == 2
        assert properties.ExecutionMode == "PARALLEL"
        assert len(properties.Stages) == 2
        assert len(properties.Variables) == 1
        assert len(properties.Triggers) == 1
        assert properties.Tags == {
            "Name": "comprehensive-pipeline",
            "Environment": "production",
        }

    def test_extra_fields_are_ignored(self) -> None:
        """Test that extra fields are ignored on properties."""
        properties = PipelineProperties(
            Name="test-pipeline",
            unknownField="should-be-ignored",  # type: ignore
        )
        assert properties.Name == "test-pipeline"
        assert not hasattr(properties, "unknownField")


class TestPipeline:

    def test_initialization_with_identifier(self) -> None:
        """Test initialization with just an identifier."""
        pipeline = Pipeline(Properties=PipelineProperties(Name="test-pipeline"))
        assert pipeline.Type == "AWS::CodePipeline::Pipeline"
        assert pipeline.Properties.Name == "test-pipeline"

    def test_initialization_with_properties(self) -> None:
        """Test initialization with full properties."""
        properties = PipelineProperties(
            Name="test-pipeline",
            RoleArn="arn:aws:iam::123456789012:role/codepipeline-role",
            PipelineType="V2",
            Version=1,
        )
        pipeline = Pipeline(Properties=properties)
        assert pipeline.Properties == properties
        assert pipeline.Properties.Name == "test-pipeline"
        assert (
            pipeline.Properties.RoleArn
            == "arn:aws:iam::123456789012:role/codepipeline-role"
        )
        assert pipeline.Properties.PipelineType == "V2"
        assert pipeline.Properties.Version == 1

    def test_type_is_fixed(self) -> None:
        """Test that Type is always the same for all instances."""
        pipeline1 = Pipeline(Properties=PipelineProperties(Name="pipeline-1"))
        pipeline2 = Pipeline(Properties=PipelineProperties(Name="pipeline-2"))
        assert pipeline1.Type == "AWS::CodePipeline::Pipeline"
        assert pipeline2.Type == "AWS::CodePipeline::Pipeline"

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        pipeline = Pipeline(Properties=PipelineProperties(Name="test-pipeline"))
        data = pipeline.dict(exclude_none=True)
        assert data["Type"] == "AWS::CodePipeline::Pipeline"
        assert data["Properties"]["Name"] == "test-pipeline"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default_factory correctly."""
        pipeline1 = Pipeline(Properties=PipelineProperties(Name="pipeline-1"))
        pipeline2 = Pipeline(Properties=PipelineProperties(Name="pipeline-2"))
        assert pipeline1.Properties is not pipeline2.Properties
        assert pipeline1.Properties.Name == "pipeline-1"
        assert pipeline2.Properties.Name == "pipeline-2"

    def test_complex_properties_serialization(self) -> None:
        """Test serialization of complex nested properties."""
        properties = PipelineProperties(
            Name="complex-pipeline",
            ArtifactStore=PipelineArtifactStore(
                location="artifact-bucket",
                type="S3",
                encryptionKey={"id": "alias/aws/s3", "type": "KMS"},
            ),
            Stages=[
                PipelineStage(
                    name="Source",
                    actions=[
                        {
                            "name": "SourceAction",
                            "actionTypeId": {
                                "category": "Source",
                                "owner": "AWS",
                                "provider": "S3",
                                "version": "1",
                            },
                        }
                    ],
                ),
                PipelineStage(
                    name="Deploy",
                    actions=[
                        {
                            "name": "DeployAction",
                            "actionTypeId": {
                                "category": "Deploy",
                                "owner": "AWS",
                                "provider": "CodeDeploy",
                                "version": "1",
                            },
                        }
                    ],
                ),
            ],
            Tags={
                "Environment": "production",
                "Project": "web-app",
            },
        )
        pipeline = Pipeline(Properties=properties)

        data = pipeline.dict(exclude_none=True)
        assert data["Properties"]["ArtifactStore"]["location"] == "artifact-bucket"
        assert data["Properties"]["ArtifactStore"]["type"] == "S3"
        assert (
            data["Properties"]["ArtifactStore"]["encryptionKey"]["id"]
            == "alias/aws/s3"
        )
        assert len(data["Properties"]["Stages"]) == 2
        assert data["Properties"]["Stages"][0]["name"] == "Source"
        assert data["Properties"]["Stages"][1]["name"] == "Deploy"
        assert len(data["Properties"]["Tags"]) == 2
        assert data["Properties"]["Tags"]["Environment"] == "production"
        assert data["Properties"]["Tags"]["Project"] == "web-app"
