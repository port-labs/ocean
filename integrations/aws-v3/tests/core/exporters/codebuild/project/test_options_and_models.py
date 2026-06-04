import pytest
from pydantic import ValidationError
from aws.core.exporters.codebuild.project.models import (
    CodeBuildProject,
    ProjectProperties,
    SingleCodeBuildProjectRequest,
    PaginatedCodeBuildProjectRequest,
)


def test_project_properties_creation() -> None:
    """Test ProjectProperties model creation."""
    props = ProjectProperties(
        name="test-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/test-project",
        description="Test CodeBuild project",
    )

    assert props.name == "test-project"
    assert props.arn == "arn:aws:codebuild:us-east-1:123456789012:project/test-project"
    assert props.description == "Test CodeBuild project"


def test_project_properties_default_values() -> None:
    """Test ProjectProperties model with default values."""
    props = ProjectProperties()

    assert props.name == ""
    assert props.arn == ""
    assert props.description is None
    assert props.tags == []
    assert props.secondarySources == []
    assert props.secondaryArtifacts == []


def test_codebuild_project_creation() -> None:
    """Test CodeBuildProject resource model creation."""
    project = CodeBuildProject()

    assert project.Type == "AWS::CodeBuild::Project"
    assert isinstance(project.Properties, ProjectProperties)


def test_codebuild_project_with_properties() -> None:
    """Test CodeBuildProject with custom properties."""
    props = ProjectProperties(
        name="test-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/test-project",
    )
    project = CodeBuildProject(Properties=props)

    assert project.Type == "AWS::CodeBuild::Project"
    assert project.Properties.name == "test-project"
    assert (
        project.Properties.arn
        == "arn:aws:codebuild:us-east-1:123456789012:project/test-project"
    )


def test_single_codebuild_project_request_creation() -> None:
    """Test SingleCodeBuildProjectRequest creation."""
    request = SingleCodeBuildProjectRequest(
        region="us-east-1",
        account_id="123456789012",
        project_name="test-project",
        include=["GetProjectDetailsAction"],
    )

    assert request.region == "us-east-1"
    assert request.account_id == "123456789012"
    assert request.project_name == "test-project"
    assert request.include == ["GetProjectDetailsAction"]


def test_single_codebuild_project_request_missing_project_name() -> None:
    """Test SingleCodeBuildProjectRequest validation fails without project_name."""
    with pytest.raises(ValidationError) as exc_info:
        SingleCodeBuildProjectRequest(
            region="us-east-1", account_id="123456789012"
        )  # type: ignore

    assert "project_name" in str(exc_info.value)


def test_paginated_codebuild_project_request_creation() -> None:
    """Test PaginatedCodeBuildProjectRequest creation."""
    request = PaginatedCodeBuildProjectRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )

    assert request.region == "us-east-1"
    assert request.account_id == "123456789012"
    assert request.include == []


def test_paginated_codebuild_project_request_default_include() -> None:
    """Test PaginatedCodeBuildProjectRequest with default include."""
    request = PaginatedCodeBuildProjectRequest(
        region="us-east-1", account_id="123456789012"
    )

    assert request.include == []


def test_project_properties_with_complex_objects() -> None:
    """Test ProjectProperties with nested complex objects."""
    environment = dict(
        type="LINUX_CONTAINER",
        image="aws/codebuild/amazonlinux2-x86_64-standard:3.0",
        computeType="BUILD_GENERAL1_MEDIUM",
    )

    source = dict(
        type="GITHUB", location="https://github.com/example/repo.git"
    )

    artifacts = dict(type="NO_ARTIFACTS")

    props = ProjectProperties(
        name="complex-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/complex-project",
        environment=environment,
        source=source,
        artifacts=artifacts,
        timeoutInMinutes=60,
        concurrentBuildLimit=5,
    )

    assert props.name == "complex-project"
    assert props.environment['type'] == "LINUX_CONTAINER"
    assert props.source['type'] == "GITHUB"
    assert props.artifacts['type'] == "NO_ARTIFACTS"
    assert props.timeoutInMinutes == 60
    assert props.concurrentBuildLimit == 5


def test_project_properties_ignore_extra_fields() -> None:
    """Test that ProjectProperties forbids extra fields."""
    props = ProjectProperties(
        name="test-project",
        arn="arn:aws:codebuild:us-east-1:123456789012:project/test-project",
        invalid_field="should_not_be_allowed",  # type: ignore
    )

    assert "invalid_field" not in props.dict()
