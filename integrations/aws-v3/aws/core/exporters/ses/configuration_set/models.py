from typing import Any
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class ConfigurationSetProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="ignore")

    ConfigurationSetName: str | None = None
    TrackingOptions: dict[str, Any] | None = None
    DeliveryOptions: dict[str, Any] | None = None
    ReputationOptions: dict[str, Any] | None = None
    SendingOptions: dict[str, Any] | None = None
    Tags: list[dict[str, str]] | None = None
    SuppressionOptions: dict[str, Any] | None = None
    VdmOptions: dict[str, Any] | None = None
    ArchivingOptions: dict[str, Any] | None = None


class ConfigurationSet(ResourceModel[ConfigurationSetProperties]):
    Type: str = "AWS::SES::ConfigurationSet"
    Properties: ConfigurationSetProperties = Field(
        default_factory=ConfigurationSetProperties
    )


class SingleConfigurationSetRequest(ResourceRequestModel):
    """Options for exporting a single SES configuration set."""

    configuration_set_name: str = Field(
        ..., description="The name of the SES configuration set to export"
    )


class PaginatedConfigurationSetRequest(ResourceRequestModel):
    """Options for exporting all SES configuration sets in a region."""

    pass
