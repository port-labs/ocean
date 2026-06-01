import pytest
from pydantic import ValidationError
from aws.core.exporters.codebuild.project.models import (
    CodeBuildProject,
    ProjectProperties,
    SingleCodeBuildProjectRequest,
    PaginatedCodeBuildProjectRequest,
    ProjectEnvironment,
    ProjectSource,
    ProjectArtifacts,
    ProjectVpcConfig,
)


def test_project_properties_creation():
    """Test ProjectProperties model creation."""
    props = ProjectProperties(
        name="test-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/test-project",
        description="Test CodeBuild project"
    )
    
    assert props.name == "test-project"
    assert props.arn == "arn:aws:codebuild:us-east-1:123456789012:project/test-project"
    assert props.description == "Test CodeBuild project"


def test_project_properties_default_values():
    """Test ProjectProperties model with default values."""
    props = ProjectProperties()
    
    assert props.name == ""
    assert props.arn == ""
    assert props.description is None
    assert props.tags == []
    assert props.secondarySources == []
    assert props.secondaryArtifacts == []


def test_project_environment_creation():
    """Test ProjectEnvironment model creation."""
    env = ProjectEnvironment(
        type="LINUX_CONTAINER",
        image="aws/codebuild/amazonlinux2-x86_64-standard:3.0",
        computeType="BUILD_GENERAL1_MEDIUM",
        privilegedMode=False
    )
    
    assert env.type == "LINUX_CONTAINER"
    assert env.image == "aws/codebuild/amazonlinux2-x86_64-standard:3.0"
    assert env.computeType == "BUILD_GENERAL1_MEDIUM"
    assert env.privilegedMode is False
    assert env.environmentVariables == []


def test_project_source_creation():
    """Test ProjectSource model creation."""
    source = ProjectSource(
        type="GITHUB",
        location="https://github.com/example/repo.git",
        gitCloneDepth=1,
        reportBuildStatus=True
    )
    
    assert source.type == "GITHUB"
    assert source.location == "https://github.com/example/repo.git"
    assert source.gitCloneDepth == 1
    assert source.reportBuildStatus is True


def test_project_artifacts_creation():
    """Test ProjectArtifacts model creation."""
    artifacts = ProjectArtifacts(
        type="S3",
        location="my-bucket/artifacts",
        namespaceType="BUILD_ID",
        name="artifacts.zip",
        packaging="ZIP"
    )
    
    assert artifacts.type == "S3"
    assert artifacts.location == "my-bucket/artifacts"
    assert artifacts.namespaceType == "BUILD_ID"
    assert artifacts.name == "artifacts.zip"
    assert artifacts.packaging == "ZIP"


def test_project_vpc_config_creation():
    """Test ProjectVpcConfig model creation."""
    vpc_config = ProjectVpcConfig(
        vpcId="vpc-12345678",
        subnets=["subnet-12345", "subnet-67890"],
        securityGroupIds=["sg-12345", "sg-67890"]
    )
    
    assert vpc_config.vpcId == "vpc-12345678"
    assert vpc_config.subnets == ["subnet-12345", "subnet-67890"]
    assert vpc_config.securityGroupIds == ["sg-12345", "sg-67890"]


def test_codebuild_project_creation():
    """Test CodeBuildProject resource model creation."""
    project = CodeBuildProject()
    
    assert project.Type == "AWS::CodeBuild::Project"
    assert isinstance(project.Properties, ProjectProperties)


def test_codebuild_project_with_properties():
    """Test CodeBuildProject with custom properties."""
    props = ProjectProperties(
        name="test-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/test-project"
    )
    project = CodeBuildProject(Properties=props)
    
    assert project.Type == "AWS::CodeBuild::Project"
    assert project.Properties.name == "test-project"
    assert project.Properties.arn == "arn:aws:codebuild:us-east-1:123456789012:project/test-project"


def test_single_codebuild_project_request_creation():
    """Test SingleCodeBuildProjectRequest creation."""
    request = SingleCodeBuildProjectRequest(
        region="us-east-1",
        account_id="123456789012",
        project_name="test-project",
        include=["GetProjectDetailsAction"]
    )
    
    assert request.region == "us-east-1"
    assert request.account_id == "123456789012"
    assert request.project_name == "test-project"
    assert request.include == ["GetProjectDetailsAction"]


def test_single_codebuild_project_request_missing_project_name():
    """Test SingleCodeBuildProjectRequest validation fails without project_name."""
    with pytest.raises(ValidationError) as exc_info:
        SingleCodeBuildProjectRequest(
            region="us-east-1",
            account_id="123456789012"
        )
    
    assert "project_name" in str(exc_info.value)


def test_paginated_codebuild_project_request_creation():
    """Test PaginatedCodeBuildProjectRequest creation."""
    request = PaginatedCodeBuildProjectRequest(
        region="us-east-1",
        account_id="123456789012",
        include=[]
    )
    
    assert request.region == "us-east-1"
    assert request.account_id == "123456789012"
    assert request.include == []


def test_paginated_codebuild_project_request_default_include():
    """Test PaginatedCodeBuildProjectRequest with default include."""
    request = PaginatedCodeBuildProjectRequest(
        region="us-east-1",
        account_id="123456789012"
    )
    
    assert request.include == []


def test_project_properties_with_complex_objects():
    """Test ProjectProperties with nested complex objects."""
    environment = ProjectEnvironment(
        type="LINUX_CONTAINER",
        image="aws/codebuild/amazonlinux2-x86_64-standard:3.0",
        computeType="BUILD_GENERAL1_MEDIUM"
    )
    
    source = ProjectSource(
        type="GITHUB",
        location="https://github.com/example/repo.git"
    )
    
    artifacts = ProjectArtifacts(
        type="NO_ARTIFACTS"
    )
    
    props = ProjectProperties(
        name="complex-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/complex-project",
        environment=environment,
        source=source,
        artifacts=artifacts,
        timeoutInMinutes=60,
        concurrentBuildLimit=5
    )
    
    assert props.name == "complex-project"
    assert props.environment.type == "LINUX_CONTAINER"
    assert props.source.type == "GITHUB"
    assert props.artifacts.type == "NO_ARTIFACTS"
    assert props.timeoutInMinutes == 60
    assert props.concurrentBuildLimit == 5


def test_project_properties_ignore_extra_fields():
    """Test that ProjectProperties forbids extra fields."""
    props = ProjectProperties(
            name="test-project",
            arn="arn:aws:codebuild:us-east-1:123456789012:project/test-project",
            invalid_field="should_not_be_allowed"
        )

    assert 'invalid_field' not in props.dict()