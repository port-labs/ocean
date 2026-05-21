from typing import Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, root_validator
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ImageProperties(BaseModel):
    repositoryName: str = Field(default_factory=str, alias="RepositoryName")
    registryId: Optional[str] = Field(default=None, alias="RegistryId")
    imageDigest: Optional[str] = Field(default=None, alias="ImageDigest")
    imageTags: list[str] = Field(default_factory=list, alias="ImageTags")
    imageSizeInBytes: Optional[int] = Field(default=None, alias="ImageSizeInBytes")
    imagePushedAt: Optional[datetime] = Field(default=None, alias="ImagePushedAt")
    imageManifestMediaType: Optional[str] = Field(
        default=None, alias="ImageManifestMediaType"
    )
    artifactMediaType: Optional[str] = Field(default=None, alias="ArtifactMediaType")
    lastRecordedPullTime: Optional[datetime] = Field(
        default=None, alias="LastRecordedPullTime"
    )
    imageStatus: Optional[str] = Field(default=None, alias="ImageStatus")
    imageScanStatus: Optional[dict[str, Any]] = Field(
        default=None, alias="ImageScanStatus"
    )
    imageScanFindingsSummary: Optional[dict[str, Any]] = Field(
        default=None, alias="ImageScanFindingsSummary"
    )

    class Config:
        extra = "allow"
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
        default=None, description="The tag of the image to export"
    )
    image_digest: Optional[str] = Field(
        default=None, description="The digest of the image to export"
    )

    @root_validator
    def require_tag_or_digest(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values.get("image_tag") and not values.get("image_digest"):
            raise ValueError("Either image_tag or image_digest must be provided")
        return values


class PaginatedImageRequest(ResourceRequestModel):
    """Options for exporting all ECR images in a region."""

    repository_name: Optional[str] = Field(
        default=None, description="Limit images to a specific repository (optional)"
    )
    tag_status: Literal["TAGGED", "UNTAGGED", "ANY"] = Field(
        default="TAGGED",
        description="ECR DescribeImagesFilter.tagStatus value.",
    )
    image_status: Literal["ACTIVE", "ARCHIVED", "ACTIVATING", "ANY"] = Field(
        default="ACTIVE",
        description="ECR DescribeImagesFilter.imageStatus value.",
    )
