from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ImageProperties(BaseModel):
    repositoryName: str = Field(default_factory=str, alias="repositoryName")
    imageId: dict[str, Any] = Field(default_factory=dict, alias="imageId")
    imageManifest: Optional[str] = Field(default=None, alias="imageManifest")
    imageManifestMediaType: Optional[str] = Field(default=None, alias="imageManifestMediaType")
    registryId: Optional[str] = Field(default=None, alias="registryId")
    imageSizeInBytes: Optional[int] = Field(default=None, alias="imageSizeInBytes")
    imagePushedAt: Optional[datetime] = Field(default=None, alias="imagePushedAt")
    imageScanFindingsSummary: Optional[dict[str, Any]] = Field(
        default=None, alias="imageScanFindingsSummary"
    )
    imageScanningConfiguration: Optional[dict[str, Any]] = Field(
        default=None, alias="imageScanningConfiguration"
    )
    artifactMediaType: Optional[str] = Field(default=None, alias="artifactMediaType")
    lastRecordedPullTime: Optional[datetime] = Field(default=None, alias="lastRecordedPullTime")
    tags: list[dict[str, str]] = Field(default_factory=list, alias="tags")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class Image(ResourceModel[ImageProperties]):
    Type: str = "AWS::ECR::Image"
    Properties: ImageProperties = Field(default_factory=ImageProperties)


class SingleImageRequest(ResourceRequestModel):
    """Options for exporting a single ECR image."""

    repository_name: str = Field(
        ..., description="The name of the ECR repository containing the image"
    )
    image_tag: Optional[str] = Field(
        default=None, description="The tag of the image to export (optional, can use image_digest instead)"
    )
    image_digest: Optional[str] = Field(
        default=None, description="The digest of the image to export (optional, can use image_tag instead)"
    )


class PaginatedImageRequest(ResourceRequestModel):
    """Options for exporting all ECR images in a region."""

    repository_name: Optional[str] = Field(
        default=None, description="Limit images to a specific repository (optional)"
    )