from typing import Optional
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class DkimSigningAttributesModel(BaseAWSPropertiesModel):
    DomainSigningSelector: Optional[str] = None
    DomainSigningPrivateKey: Optional[str] = None
    NextSigningKeyLength: Optional[str] = None


class DkimAttributesModel(BaseAWSPropertiesModel):
    SigningEnabled: Optional[bool] = None
    Status: Optional[str] = None
    Tokens: Optional[list[str]] = None
    SigningAttributesOrigin: Optional[str] = None
    CurrentSigningKeyLength: Optional[str] = None
    LastKeyGenerationTimestamp: Optional[str] = None


class MailFromAttributesModel(BaseAWSPropertiesModel):
    MailFromDomain: Optional[str] = None
    MailFromDomainStatus: Optional[str] = None
    BehaviorOnMxFailure: Optional[str] = None


class EmailIdentityProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="forbid")

    EmailIdentity: str = Field(default_factory=str)
    IdentityType: Optional[str] = None
    FeedbackForwardingStatus: Optional[bool] = None
    VerifiedForSendingStatus: Optional[bool] = None
    DkimAttributes: Optional[DkimAttributesModel] = None
    MailFromAttributes: Optional[MailFromAttributesModel] = None
    Policies: Optional[dict[str, str]] = None
    Tags: Optional[list[dict[str, str]]] = None
    ConfigurationSetName: Optional[str] = None


class EmailIdentity(ResourceModel[EmailIdentityProperties]):
    Type: str = "AWS::SES::EmailIdentity"
    Properties: EmailIdentityProperties = Field(
        default_factory=EmailIdentityProperties
    )


class SingleEmailIdentityRequest(ResourceRequestModel):
    """Options for exporting a single SES email identity."""

    email_identity: str = Field(
        ..., description="The email identity (email address or domain) to export"
    )


class PaginatedEmailIdentityRequest(ResourceRequestModel):
    """Options for exporting all SES email identities in a region."""

    pass
