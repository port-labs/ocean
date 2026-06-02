from datetime import datetime

import pytest
from pydantic import ValidationError

from aws.core.exporters.codedeploy.application.models import (
    CodeDeployApplication,
    CodeDeployApplicationProperties,
    SingleCodeDeployApplicationRequest,
    PaginatedCodeDeployApplicationRequest,
)


class TestSingleCodeDeployApplicationRequest:

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = SingleCodeDeployApplicationRequest(
            region="us-west-2",
            account_id="123456789012",
            application_name="test-app",
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.application_name == "test-app"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["GetCodeDeployApplicationDetailsAction"]
        options = SingleCodeDeployApplicationRequest(
            region="eu-central-1",
            account_id="123456789012",
            application_name="test-app",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.application_name == "test-app"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test validation error when region is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleCodeDeployApplicationRequest(
                account_id="123456789012", application_name="test-app"
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_application_name(self) -> None:
        """Test validation error when application_name is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleCodeDeployApplicationRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "application_name" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test initialization with empty include list."""
        options = SingleCodeDeployApplicationRequest(
            region="us-east-1",
            account_id="123456789012",
            application_name="test-app",
            include=[],
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        """Test include list with multiple actions."""
        options = SingleCodeDeployApplicationRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            application_name="test-app",
            include=[
                "GetCodeDeployApplicationDetailsAction",
                "GetCodeDeployApplicationTagsAction",
            ],
        )
        assert len(options.include) == 2
        assert "GetCodeDeployApplicationDetailsAction" in options.include
        assert "GetCodeDeployApplicationTagsAction" in options.include


class TestPaginatedCodeDeployApplicationRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedCodeDeployApplicationRequest inherits properly."""
        options = PaginatedCodeDeployApplicationRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedCodeDeployApplicationRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = PaginatedCodeDeployApplicationRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include actions."""
        include_list = ["GetCodeDeployApplicationTagsAction"]
        options = PaginatedCodeDeployApplicationRequest(
            region="ap-southeast-2",
            account_id="123456789012",
            include=include_list,
        )
        assert options.region == "ap-southeast-2"
        assert options.account_id == "123456789012"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test validation error when region is missing."""
        with pytest.raises(ValidationError) as exc_info:
            PaginatedCodeDeployApplicationRequest(
                account_id="123456789012"
            )  # type: ignore
        assert "region" in str(exc_info.value)


class TestCodeDeployApplicationProperties:

    def test_initialization_empty(self) -> None:
        """Test initialization with default values."""
        properties = CodeDeployApplicationProperties()
        assert properties.ApplicationName == ""
        assert properties.ApplicationId == ""
        assert properties.CreateTime is None
        assert properties.LinkedToGitHub is None
        assert properties.GitHubAccountName is None
        assert properties.ComputePlatform is None
        assert properties.Tags == []

    def test_initialization_with_properties(self) -> None:
        """Test initialization with specific properties."""
        create_time = datetime(2023, 12, 1, 10, 30)
        properties = CodeDeployApplicationProperties(
            ApplicationName="test-app",
            ApplicationId="id-123",
            CreateTime=create_time,
            LinkedToGitHub=True,
            GitHubAccountName="octo",
            ComputePlatform="Server",
            Tags=[{"Key": "Environment", "Value": "test"}],
        )
        assert properties.ApplicationName == "test-app"
        assert properties.ApplicationId == "id-123"
        assert properties.CreateTime == create_time
        assert properties.LinkedToGitHub is True
        assert properties.GitHubAccountName == "octo"
        assert properties.ComputePlatform == "Server"
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True drops Optional Nones."""
        properties = CodeDeployApplicationProperties(
            ApplicationName="test-app",
            ApplicationId="id-1",
        )
        result = properties.dict(exclude_none=True)
        assert result["ApplicationName"] == "test-app"
        assert result["ApplicationId"] == "id-1"
        # Optional fields default to None and should be excluded
        assert "CreateTime" not in result
        assert "LinkedToGitHub" not in result
        assert "GitHubAccountName" not in result
        assert "ComputePlatform" not in result
        # Tags has a default factory of [] and is therefore included
        assert result["Tags"] == []

    def test_extra_fields_ignored(self) -> None:
        """Test that extra fields are ignored per Config."""
        properties = CodeDeployApplicationProperties(
            ApplicationName="test-app",
            unknown_field="ignored",  # type: ignore[call-arg]
        )
        assert properties.ApplicationName == "test-app"
        assert not hasattr(properties, "unknown_field")


class TestCodeDeployApplication:

    def test_initialization_with_identifier(self) -> None:
        """Test initialization with just an identifier."""
        application = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="test-app")
        )
        assert application.Type == "AWS::CodeDeploy::Application"
        assert application.Properties.ApplicationName == "test-app"

    def test_initialization_with_properties(self) -> None:
        """Test initialization with full properties."""
        properties = CodeDeployApplicationProperties(
            ApplicationName="test-app",
            ApplicationId="id-1",
            ComputePlatform="Lambda",
            LinkedToGitHub=False,
        )
        application = CodeDeployApplication(Properties=properties)
        assert application.Properties == properties
        assert application.Properties.ApplicationName == "test-app"
        assert application.Properties.ApplicationId == "id-1"
        assert application.Properties.ComputePlatform == "Lambda"
        assert application.Properties.LinkedToGitHub is False

    def test_type_is_fixed(self) -> None:
        """Test that Type is always the same for all instances."""
        app1 = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-1")
        )
        app2 = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-2")
        )
        assert app1.Type == "AWS::CodeDeploy::Application"
        assert app2.Type == "AWS::CodeDeploy::Application"

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        application = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="test-app")
        )
        data = application.dict(exclude_none=True)
        assert data["Type"] == "AWS::CodeDeploy::Application"
        assert data["Properties"]["ApplicationName"] == "test-app"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default_factory correctly."""
        app1 = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-1")
        )
        app2 = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-2")
        )
        assert app1.Properties is not app2.Properties
        assert app1.Properties.ApplicationName == "app-1"
        assert app2.Properties.ApplicationName == "app-2"

    def test_complex_properties_serialization(self) -> None:
        """Test serialization of nested Tags property."""
        properties = CodeDeployApplicationProperties(
            ApplicationName="complex-app",
            Tags=[
                {"Key": "Environment", "Value": "production"},
                {"Key": "Project", "Value": "web-app"},
            ],
        )
        application = CodeDeployApplication(Properties=properties)

        data = application.dict(exclude_none=True)
        assert data["Properties"]["ApplicationName"] == "complex-app"
        assert len(data["Properties"]["Tags"]) == 2
        assert data["Properties"]["Tags"][0]["Key"] == "Environment"
        assert data["Properties"]["Tags"][0]["Value"] == "production"
