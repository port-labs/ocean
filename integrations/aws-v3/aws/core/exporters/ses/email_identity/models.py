from typing import Any
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class EmailIdentityProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="ignore")

    IdentityName: str | None = None
    IdentityType: str | None = None
    SendingEnabled: bool | None = None
    FeedbackForwardingStatus: bool | None = None
    VerifiedForSendingStatus: bool | None = None
    DkimAttributes: dict[str, Any] | None = None
    MailFromAttributes: dict[str, Any] | None = None
    Policies: dict[str, Any] | None = None
    Tags: list[dict[str, str]] | None = None
    ConfigurationSetName: str | None = None
    VerificationStatus: str | None = None
    VerificationInfo: dict[str, Any] | None = None


class EmailIdentity(ResourceModel[EmailIdentityProperties]):
    Type: str = "AWS::SES::EmailIdentity"
    Properties: EmailIdentityProperties = Field(default_factory=EmailIdentityProperties)


class SingleEmailIdentityRequest(ResourceRequestModel):
    """Options for exporting a single SES email identity."""

    identity_name: str = Field(
        ..., description="The email identity (email address or domain) to export"
    )


class PaginatedEmailIdentityRequest(ResourceRequestModel):
    """Options for exporting all SES email identities in a region."""

    pass
