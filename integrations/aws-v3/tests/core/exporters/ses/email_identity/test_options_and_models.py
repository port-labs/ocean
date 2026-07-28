import pytest
from pydantic import ValidationError

from aws.core.exporters.ses.email_identity.models import (
    EmailIdentityProperties,
    EmailIdentity,
    SingleEmailIdentityRequest,
    PaginatedEmailIdentityRequest,
)


class TestSingleEmailIdentityRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleEmailIdentityRequest(
            region="us-east-1",
            account_id="123456789012",
            email_identity="example.com",
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.email_identity == "example.com"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["GetEmailIdentityAction"]
        options = SingleEmailIdentityRequest(
            region="eu-west-1",
            account_id="123456789012",
            email_identity="user@example.com",
            include=include_list,
        )
        assert options.region == "eu-west-1"
        assert options.account_id == "123456789012"
        assert options.email_identity == "user@example.com"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleEmailIdentityRequest(
                account_id="123456789012",
                email_identity="example.com",
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_email_identity(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleEmailIdentityRequest(
                region="us-east-1",
                account_id="123456789012",
            )  # type: ignore
        assert "email_identity" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        options = SingleEmailIdentityRequest(
            region="us-east-1",
            account_id="123456789012",
            email_identity="example.com",
            include=[],
        )
        assert options.include == []


class TestPaginatedEmailIdentityRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedEmailIdentityRequest inherits from the base class."""
        from aws.core.modeling.resource_models import ResourceRequestModel

        assert issubclass(PaginatedEmailIdentityRequest, ResourceRequestModel)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedEmailIdentityRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["GetEmailIdentityAction"]
        options = PaginatedEmailIdentityRequest(
            region="us-east-1",
            account_id="123456789012",
            include=include_list,
        )
        assert options.include == include_list


class TestEmailIdentityProperties:

    def test_initialization_empty(self) -> None:
        """Test EmailIdentityProperties with no arguments."""
        props = EmailIdentityProperties()
        assert props.EmailIdentity == ""
        assert props.IdentityName is None
        assert props.IdentityType is None
        assert props.SendingEnabled is None
        assert props.FeedbackForwardingStatus is None
        assert props.VerifiedForSendingStatus is None
        assert props.Tags == []

    def test_initialization_with_properties(self) -> None:
        """Test EmailIdentityProperties with specific values."""
        props = EmailIdentityProperties(
            EmailIdentity="example.com",
            IdentityName="example.com",
            IdentityType="DOMAIN",
            SendingEnabled=True,
            VerifiedForSendingStatus=True,
            VerificationStatus="SUCCESS",
        )
        assert props.EmailIdentity == "example.com"
        assert props.IdentityName == "example.com"
        assert props.IdentityType == "DOMAIN"
        assert props.SendingEnabled is True
        assert props.VerifiedForSendingStatus is True
        assert props.VerificationStatus == "SUCCESS"

    def test_rejects_unknown_fields(self) -> None:
        """Extra fields not present on either the list or get API responses still raise."""
        with pytest.raises(ValidationError):
            EmailIdentityProperties(EmailIdentity="example.com", SomeUnknownField="x")  # type: ignore[call-arg]

    def test_tags_default_empty_list(self) -> None:
        """Test that Tags defaults to an empty list."""
        props = EmailIdentityProperties()
        assert props.Tags == []

    def test_tags_with_values(self) -> None:
        """Test Tags field with values."""
        props = EmailIdentityProperties(
            EmailIdentity="example.com",
            Tags=[{"Key": "Environment", "Value": "production"}],
        )
        assert len(props.Tags) == 1
        assert props.Tags[0]["Key"] == "Environment"

    def test_dict_exclude_none(self) -> None:
        """Test that dict() excludes None values."""
        props = EmailIdentityProperties(EmailIdentity="example.com")

        props_dict = props.model_dump(exclude_none=True)

        assert "IdentityType" not in props_dict
        assert "VerifiedForSendingStatus" not in props_dict
        assert props_dict["EmailIdentity"] == "example.com"


class TestEmailIdentity:

    def test_initialization_defaults(self) -> None:
        """Test EmailIdentity with default values."""
        identity = EmailIdentity()
        assert identity.Type == "AWS::SES::EmailIdentity"
        assert identity.Properties is not None

    def test_initialization_with_properties(self) -> None:
        """Test EmailIdentity initialization with properties."""
        props = EmailIdentityProperties(
            EmailIdentity="example.com",
            IdentityType="DOMAIN",
        )
        identity = EmailIdentity(Properties=props)
        assert identity.Type == "AWS::SES::EmailIdentity"
        assert identity.Properties.EmailIdentity == "example.com"
        assert identity.Properties.IdentityType == "DOMAIN"

    def test_type_is_fixed(self) -> None:
        """Test that the Type field is fixed."""
        identity = EmailIdentity()
        assert identity.Type == "AWS::SES::EmailIdentity"

    def test_properties_default_factory(self) -> None:
        """Test that Properties has a default factory."""
        identity1 = EmailIdentity()
        identity2 = EmailIdentity()
        assert identity1.Properties is not identity2.Properties
