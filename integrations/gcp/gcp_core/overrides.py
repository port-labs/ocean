from typing import Any, ClassVar, Literal


from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic.v1 import Field, BaseModel


class GCPCloudResourceSelector(Selector):
    resource_kinds: list[str] = Field(
        alias="resourceKinds",
        min_items=1,
        title="Resource Kinds",
        description="List of GCP resource kinds to fetch via the Cloud Resource API.",
    )


class GCPCloudResourceConfig(ResourceConfig):
    kind: Literal["cloudResource"] = Field(
        title="GCP Cloud Resource",
        description="GCP cloud resource kind.",
    )
    selector: GCPCloudResourceSelector = Field(
        title="Cloud Resource Selector",
        description="Selector for the GCP cloud resource.",
    )


class GCPResourceSelector(Selector):
    preserve_api_response_case_style: bool | None = Field(
        default=None,
        alias="preserveApiResponseCaseStyle",
        title="Preserve API Response Case Style",
        description=(
            "Controls whether to preserve the Google Cloud API's original field format instead of using protobuf's default snake case. "
            "When False (default): Uses protobuf's default snake_case format (existing behavior). "
            "When True: Preserves the specific API's original format (e.g., camelCase for PubSub). "
            "If not set, defaults to False to maintain existing behavior (snake_case for all APIs)."
            "Note that this setting does not affect resources fetched from the cloud asset API"
        ),
    )


class GCPTopicResourceConfig(ResourceConfig):
    kind: Literal["pubsub.googleapis.com/Topic"] = Field(
        title="GCP PubSub Topic",
        description="GCP PubSub Topic resource kind.",
    )
    selector: GCPResourceSelector = Field(
        title="Topic Selector",
        description="Selector for the GCP PubSub Topic resource.",
    )


class GCPSubscriptionResourceConfig(ResourceConfig):
    kind: Literal["pubsub.googleapis.com/Subscription"] = Field(
        title="GCP PubSub Subscription",
        description="GCP PubSub Subscription resource kind.",
    )
    selector: GCPResourceSelector = Field(
        title="Subscription Selector",
        description="Selector for the GCP PubSub Subscription resource.",
    )


class GCPProjectResourceConfig(ResourceConfig):
    kind: Literal["cloudresourcemanager.googleapis.com/Project"] = Field(
        title="GCP Project",
        description="GCP Project resource kind.",
    )
    selector: GCPResourceSelector = Field(
        title="Project Selector",
        description="Selector for the GCP Project resource.",
    )


class GCPOrganizationResourceConfig(ResourceConfig):
    kind: Literal["cloudresourcemanager.googleapis.com/Organization"] = Field(
        title="GCP Organization",
        description="GCP Organization resource kind.",
    )
    selector: GCPResourceSelector = Field(
        title="Organization Selector",
        description="Selector for the GCP Organization resource.",
    )


class GCPFolderResourceConfig(ResourceConfig):
    kind: Literal["cloudresourcemanager.googleapis.com/Folder"] = Field(
        title="GCP Folder",
        description="GCP Folder resource kind.",
    )
    selector: GCPResourceSelector = Field(
        title="Folder Selector",
        description="Selector for the GCP Folder resource.",
    )


class GCPResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Kind",
        description="Use this to map GCP resources supported by the <a target='_blank' href='https://docs.cloud.google.com/asset-inventory/docs/asset-types'>GCP Asset Inventory API</a> by setting the kind name to the full resource type.\n\nExample: compute.googleapis.com/Instance",
    )
    selector: GCPResourceSelector = Field(
        title="Selector",
        description="Selector for the custom GCP resource.",
    )


class GCPCloudFunctionSelector(Selector):
    query: str = Field(default="true", title="Query", description="JQ filter applied to results returned by the cloud function.")
    function_url: str = Field(
        alias="functionUrl",
        title="Function URL",
        description="URL of the HTTP endpoint implementing the cloud-function sync protocol (e.g. a Cloud Run service).",
    )
    secrets: dict[str, Any] = Field(
        default_factory=dict,
        title="Secrets",
        description="Key-value pairs forwarded to the endpoint in every request body. Use for upstream API credentials.",
    )


class GCPCloudFunctionResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Kind",
        description="Resource kind name — forwarded to the cloud function as the `kind` field so the function can route internally.",
    )
    selector: GCPCloudFunctionSelector = Field(
        title="Cloud Function Selector",
        description="Selector for a resource served by the cloud-function sync protocol.",
    )


class GCPPortAppConfig(PortAppConfig):
    allow_custom_kinds: ClassVar[bool] = True

    resources: list[
        GCPCloudResourceConfig
        | GCPTopicResourceConfig
        | GCPSubscriptionResourceConfig
        | GCPProjectResourceConfig
        | GCPOrganizationResourceConfig
        | GCPFolderResourceConfig
        | GCPCloudFunctionResourceConfig
        | GCPResourceConfig
    ] = Field(
        title="Resources",
        description="Configuration of resources to be synchronized by this app.",
        default_factory=list,
    )  # type: ignore[assignment]


class ProtoConfig(BaseModel):
    preserving_proto_field_name: bool | None = None
