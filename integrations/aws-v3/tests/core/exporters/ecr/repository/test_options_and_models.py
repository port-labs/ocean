import pytest
from pydantic import ValidationError
from datetime import datetime

from aws.core.exporters.ecr.repository.models import (
    Repository,
    RepositoryProperties,
    SingleRepositoryRequest,
    PaginatedRepositoryRequest,
)


class TestExporterOptions:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleRepositoryRequest(
            region="us-west-2", account_id="123456789012", repository_name="my-repo"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.repository_name == "my-repo"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["GetRepositoryPolicyAction"]
        options = SingleRepositoryRequest(
            region="eu-central-1",
            account_id="123456789012",
            repository_name="my-repo",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.repository_name == "my-repo"
        assert options.include == include_list

    def test_missing_required_repository_name(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleRepositoryRequest(region="us-west-2", account_id="123456789012")  # type: ignore
        assert "repository_name" in str(exc_info.value)


class TestPaginatedRepositoryRequest:

    def test_inheritance(self) -> None:
        options = PaginatedRepositoryRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedRepositoryRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedRepositoryRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["GetRepositoryPolicyAction"]
        options = PaginatedRepositoryRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )
        assert options.region == "ap-southeast-2"
        assert options.include == include_list


class TestRepositoryProperties:

    def test_initialization_empty(self) -> None:
        properties = RepositoryProperties()
        assert properties.repositoryName == ""
        assert properties.repositoryArn == ""
        assert properties.repositoryUri == ""
        assert properties.registryId is None
        assert properties.createdAt is None
        assert properties.tags == []

    def test_initialization_with_properties(self) -> None:
        properties = RepositoryProperties(
            repositoryName="my-repo",
            repositoryArn="arn:aws:ecr:us-east-1:123456789012:repository/my-repo",
            repositoryUri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo",
            imageTagMutability="MUTABLE",
            tags=[{"Key": "Environment", "Value": "test"}],
        )
        assert properties.repositoryName == "my-repo"
        assert properties.imageTagMutability == "MUTABLE"
        assert properties.tags == [{"Key": "Environment", "Value": "test"}]

    def test_dict_exclude_none(self) -> None:
        properties = RepositoryProperties(
            repositoryName="my-repo",
            tags=[{"Key": "Project", "Value": "demo"}],
        )
        result = properties.dict(by_alias=True, exclude_none=True)
        assert result["RepositoryName"] == "my-repo"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]
        assert "RegistryId" not in result

    def test_all_properties_assignment(self) -> None:
        properties = RepositoryProperties(
            repositoryName="my-repo",
            repositoryArn="arn:aws:ecr:us-east-1:123456789012:repository/my-repo",
            repositoryUri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo",
            registryId="123456789012",
            createdAt=datetime(2025, 1, 1, 0, 0, 0),
            imageTagMutability="IMMUTABLE",
            imageScanningConfiguration={"scanOnPush": True},
            encryptionConfiguration={"encryptionType": "AES256"},
            lifecyclePolicy={"rules": [{"rulePriority": 1}]},
            repositoryPolicyText='{"Version": "2012-10-17"}',
            tags=[{"Key": "Name", "Value": "server"}],
        )
        assert properties.repositoryName == "my-repo"
        assert properties.imageTagMutability == "IMMUTABLE"
        assert properties.tags == [{"Key": "Name", "Value": "server"}]


class TestRepository:

    def test_initialization_with_identifier(self) -> None:
        repository = Repository(
            Properties=RepositoryProperties(repositoryName="my-repo")
        )
        assert repository.Type == "AWS::ECR::Repository"
        assert repository.Properties.repositoryName == "my-repo"

    def test_initialization_with_properties(self) -> None:
        properties = RepositoryProperties(
            repositoryName="my-repo",
            imageTagMutability="MUTABLE",
        )
        repository = Repository(Properties=properties)
        assert repository.Properties == properties
        assert repository.Properties.repositoryName == "my-repo"
        assert repository.Properties.imageTagMutability == "MUTABLE"

    def test_type_is_fixed(self) -> None:
        repo1 = Repository(Properties=RepositoryProperties(repositoryName="repo1"))
        repo2 = Repository(Properties=RepositoryProperties(repositoryName="repo2"))
        assert repo1.Type == "AWS::ECR::Repository"
        assert repo2.Type == "AWS::ECR::Repository"

    def test_dict_exclude_none(self) -> None:
        repository = Repository(
            Properties=RepositoryProperties(repositoryName="my-repo")
        )
        data = repository.dict(by_alias=True, exclude_none=True)
        assert data["Type"] == "AWS::ECR::Repository"
        assert data["Properties"]["RepositoryName"] == "my-repo"

    def test_properties_default_factory(self) -> None:
        repo1 = Repository(Properties=RepositoryProperties(repositoryName="repo1"))
        repo2 = Repository(Properties=RepositoryProperties(repositoryName="repo2"))
        assert repo1.Properties is not repo2.Properties
        assert repo1.Properties.repositoryName == "repo1"
        assert repo2.Properties.repositoryName == "repo2"
