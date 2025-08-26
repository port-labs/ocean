import pytest
from pydantic import ValidationError

from aws.core.exporters.organizations.account.models import (
    Account,
    AccountProperties,
    SingleAccountRequest,
    PaginatedAccountRequest,
)
from aws.auth.types import AccountInfo


class TestAccountOptions:

    def test_single_options_validation(self) -> None:
        """Test SingleAccountRequest validation."""

        # Valid options
        account_info: AccountInfo = {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
            "Name": "Test Account",
            "Email": "test@example.com",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": 1672531200,
            "Status": "ACTIVE",
        }

        options = SingleAccountRequest(
            region="us-east-1",
            account_id="123456789012",
            account_data=account_info,
            include=["ListTagsAction"],
        )

        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.account_data == account_info
        assert options.include == ["ListTagsAction"]

    def test_single_options_validation_missing_account_id(self) -> None:
        """Test SingleAccountRequest validation with missing account_id."""

        account_info: AccountInfo = {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
        }

        with pytest.raises(ValidationError):
            SingleAccountRequest(  # type: ignore[call-arg]
                region="us-east-1",
                # Missing account_id
                account_data=account_info,
                include=[],
            )

    def test_single_options_validation_missing_account_data(self) -> None:
        """Test SingleAccountRequest validation with missing account_data."""
        with pytest.raises(ValidationError):
            SingleAccountRequest(  # type: ignore[call-arg]
                region="us-east-1",
                account_id="123456789012",
                # Missing account_data
                include=[],
            )

    def test_single_options_validation_empty_include(self) -> None:
        """Test SingleAccountRequest validation with empty include."""

        account_info: AccountInfo = {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
        }

        options = SingleAccountRequest(
            region="us-east-1",
            account_id="123456789012",
            account_data=account_info,
            include=[],
        )

        assert options.include == []

    def test_paginated_options_validation(self) -> None:
        """Test PaginatedAccountRequest validation."""

        account_info: AccountInfo = {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
        }

        # Valid options
        options = PaginatedAccountRequest(
            region="us-east-1", account_data=account_info, include=["ListTagsAction"]
        )

        assert options.region == "us-east-1"
        assert options.account_data == account_info
        assert options.include == ["ListTagsAction"]

    def test_paginated_options_validation_empty_include(self) -> None:
        """Test PaginatedAccountRequest validation with empty include."""

        account_info: AccountInfo = {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
        }

        options = PaginatedAccountRequest(
            region="us-east-1", account_data=account_info, include=[]
        )

        assert options.include == []

    def test_options_inheritance(self) -> None:
        """Test options inherit from ResourceRequestModel."""

        account_info: AccountInfo = {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
        }

        single_options = SingleAccountRequest(
            region="us-east-1",
            account_id="123456789012",
            account_data=account_info,
        )

        paginated_options = PaginatedAccountRequest(
            region="us-east-1",
            account_data=account_info,
        )

        # Both should have region and include fields
        assert hasattr(single_options, "region")
        assert hasattr(single_options, "include")
        assert hasattr(paginated_options, "region")
        assert hasattr(paginated_options, "include")


class TestAccountModels:

    def test_account_properties_validation(self) -> None:
        """Test AccountProperties validation."""
        # Valid properties
        properties = AccountProperties(
            Id="123456789012",
            Arn="arn:aws:organizations::123456789012:account/123456789012",
            Name="Test Account",
            Email="test@example.com",
            JoinedMethod="INVITED",
            JoinedTimestamp=1672531200,
            Status="ACTIVE",
        )

        assert properties.Id == "123456789012"
        assert (
            properties.Arn == "arn:aws:organizations::123456789012:account/123456789012"
        )
        assert properties.Name == "Test Account"
        assert properties.Email == "test@example.com"
        assert properties.JoinedMethod == "INVITED"
        assert properties.JoinedTimestamp == 1672531200
        assert properties.Status == "ACTIVE"

    def test_account_properties_validation_with_complex_fields(self) -> None:
        """Test AccountProperties validation with complex fields."""
        properties = AccountProperties(
            Id="123456789012",
            Arn="arn:aws:organizations::123456789012:account/123456789012",
            Name="Test Account",
            Email="test@example.com",
            Tags=[{"Key": "Environment", "Value": "production"}],
        )

        assert properties.Tags == [{"Key": "Environment", "Value": "production"}]

    def test_account_properties_validation_extra_forbid(self) -> None:
        """Test AccountProperties extra='forbid' behavior."""
        # Should not allow extra fields
        with pytest.raises(ValidationError):
            AccountProperties(  # type: ignore[call-arg]
                Id="123456789012",
                Arn="arn:aws:organizations::123456789012:account/123456789012",
                unknownField="unknown-value",  # This should cause validation error
            )

    def test_account_validation(self) -> None:
        """Test Account validation."""
        # Valid account
        account = Account(
            Properties=AccountProperties(
                Id="123456789012",
                Arn="arn:aws:organizations::123456789012:account/123456789012",
                Name="Test Account",
                Status="ACTIVE",
            )
        )

        assert account.Type == "AWS::Organizations::Account"
        assert account.Properties.Id == "123456789012"
        assert (
            account.Properties.Arn
            == "arn:aws:organizations::123456789012:account/123456789012"
        )
        assert account.Properties.Name == "Test Account"
        assert account.Properties.Status == "ACTIVE"

    def test_account_defaults(self) -> None:
        """Test Account default values."""
        account = Account()

        assert account.Type == "AWS::Organizations::Account"
        assert account.Properties is not None
        assert isinstance(account.Properties, AccountProperties)

    def test_account_extra_fields(self) -> None:
        """Test Account extra field handling."""
        # Should allow extra fields due to extra='ignore'
        account = Account(  # type: ignore[call-arg]
            Properties=AccountProperties(
                Id="123456789012",
                Arn="arn:aws:organizations::123456789012:account/123456789012",
            ),
            extraField="extra-value",  # This should be ignored
        )

        assert account.Type == "AWS::Organizations::Account"
        assert account.Properties.Id == "123456789012"
        assert (
            account.Properties.Arn
            == "arn:aws:organizations::123456789012:account/123456789012"
        )

    def test_account_properties_all_fields(self) -> None:
        """Test AccountProperties with all possible fields."""
        properties = AccountProperties(
            Id="123456789012",
            Arn="arn:aws:organizations::123456789012:account/123456789012",
            Name="Test Account",
            Email="test@example.com",
            JoinedMethod="INVITED",
            JoinedTimestamp=1672531200,
            Status="ACTIVE",
            Tags=[{"Key": "Environment", "Value": "production"}],
        )

        # Verify all fields are set correctly
        assert properties.Id == "123456789012"
        assert (
            properties.Arn == "arn:aws:organizations::123456789012:account/123456789012"
        )
        assert properties.Name == "Test Account"
        assert properties.Email == "test@example.com"
        assert properties.JoinedMethod == "INVITED"
        assert properties.JoinedTimestamp == 1672531200
        assert properties.Status == "ACTIVE"
        assert properties.Tags == [{"Key": "Environment", "Value": "production"}]

    def test_account_properties_none_values(self) -> None:
        """Test AccountProperties with None values."""
        properties = AccountProperties(
            Id="123456789012",
            Arn="arn:aws:organizations::123456789012:account/123456789012",
            Name=None,
            Email=None,
            Status=None,
        )

        assert properties.Id == "123456789012"
        assert (
            properties.Arn == "arn:aws:organizations::123456789012:account/123456789012"
        )
        assert properties.Name is None
        assert properties.Email is None
        assert properties.Status is None

    def test_account_dict_method(self) -> None:
        """Test Account dict() method."""
        account = Account(
            Properties=AccountProperties(
                Id="123456789012",
                Arn="arn:aws:organizations::123456789012:account/123456789012",
                Name="Test Account",
                Status="ACTIVE",
            )
        )

        account_dict = account.dict()

        assert account_dict["Type"] == "AWS::Organizations::Account"
        assert account_dict["Properties"]["Id"] == "123456789012"
        assert (
            account_dict["Properties"]["Arn"]
            == "arn:aws:organizations::123456789012:account/123456789012"
        )
        assert account_dict["Properties"]["Name"] == "Test Account"
        assert account_dict["Properties"]["Status"] == "ACTIVE"

    def test_account_dict_exclude_none(self) -> None:
        """Test Account dict() method with exclude_none=True."""
        account = Account(
            Properties=AccountProperties(
                Id="123456789012",
                Arn="arn:aws:organizations::123456789012:account/123456789012",
                Name=None,  # None value
                Status="ACTIVE",
            )
        )

        account_dict = account.dict(exclude_none=True)

        assert account_dict["Type"] == "AWS::Organizations::Account"
        assert account_dict["Properties"]["Id"] == "123456789012"
        assert (
            account_dict["Properties"]["Arn"]
            == "arn:aws:organizations::123456789012:account/123456789012"
        )
        assert account_dict["Properties"]["Status"] == "ACTIVE"
        assert "Name" not in account_dict["Properties"]  # None value excluded
