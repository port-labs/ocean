from enum import StrEnum
from typing import Any, ClassVar, Literal


from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic.v1 import Field, BaseModel, root_validator, validator


class CloudAssetContentType(StrEnum):
    RESOURCE = "RESOURCE"
    IAM_POLICY = "IAM_POLICY"
    ORG_POLICY = "ORG_POLICY"
    ACCESS_POLICY = "ACCESS_POLICY"
    OS_INVENTORY = "OS_INVENTORY"
    RELATIONSHIP = "RELATIONSHIP"


# searchAllResources and searchAllIamPolicies accept a query. listAssets does not.
SERVER_SIDE_QUERY_CONTENT_TYPES = frozenset(
    {CloudAssetContentType.RESOURCE, CloudAssetContentType.IAM_POLICY}
)

# RESOURCE sync for these kinds does not call searchAllResources.
RESOURCE_KINDS_WITHOUT_ASSET_QUERY = frozenset(
    {
        "pubsub.googleapis.com/Topic",
        "pubsub.googleapis.com/Subscription",
        "cloudresourcemanager.googleapis.com/Project",
        "cloudresourcemanager.googleapis.com/Organization",
        "cloudresourcemanager.googleapis.com/Folder",
    }
)

NON_ASSET_KINDS = frozenset({"cloudResource", "gcpCloudFunction"})


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
    content_type: Literal[
        "RESOURCE",
        "IAM_POLICY",
        "ORG_POLICY",
        "ACCESS_POLICY",
        "OS_INVENTORY",
        "RELATIONSHIP",
    ] = Field(
        default="RESOURCE",
        alias="contentType",
        title="Cloud Asset content type",
        description=(
            "Cloud Asset Inventory content type to read for this asset type. "
            "RESOURCE (default) keeps the current searchAllResources sync and the same raw resource shape. "
            "IAM_POLICY, ORG_POLICY, ACCESS_POLICY, OS_INVENTORY, and RELATIONSHIP are read with listAssets "
            "and returned as assets whose content block is iam_policy, org_policy, access_policy or access_level or service_perimeter, os_inventory, or related_asset. "
            "Expand those blocks with itemsToParse. "
            "IAM_POLICY with assetQuery uses searchAllIamPolicies instead of listAssets and still exposes iam_policy. "
            "These are explicit policies and inventory records, not Policy Analyzer effective access."
        ),
    )
    asset_query: str | None = Field(
        default=None,
        alias="assetQuery",
        title="Server-side asset query",
        description=(
            "Optional query sent to Cloud Asset Inventory. This is not the JQ selector query. "
            "It is accepted only for content types whose API has a server-side query: "
            "RESOURCE (searchAllResources) and IAM_POLICY (searchAllIamPolicies). "
            "Setting it on IAM_POLICY returns only allow-policy bindings that match the query, for example memberTypes:serviceAccount. "
            "ORG_POLICY, ACCESS_POLICY, OS_INVENTORY, and RELATIONSHIP are read with listAssets, which has no query parameter. "
            "Setting assetQuery with those content types fails config validation instead of being ignored. "
            "See <a target='_blank' href='https://cloud.google.com/asset-inventory/docs/searching-resources'>resource search syntax</a> "
            "and <a target='_blank' href='https://cloud.google.com/asset-inventory/docs/searching-iam-policies'>IAM policy search syntax</a>."
        ),
    )

    @validator("content_type", pre=True)
    def _normalize_content_type(cls, value: object) -> str:
        if value is None:
            return CloudAssetContentType.RESOURCE.value
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "contentType must be one of RESOURCE, IAM_POLICY, ORG_POLICY, "
                "ACCESS_POLICY, OS_INVENTORY, RELATIONSHIP"
            )
        return value.strip().upper()

    @validator("asset_query", pre=True)
    def _blank_asset_query_is_unset(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("assetQuery must be a string")
        stripped = value.strip()
        return stripped or None

    @root_validator
    def _asset_query_matches_content_type(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        asset_query = values.get("asset_query")
        content_type = (
            values.get("content_type") or CloudAssetContentType.RESOURCE.value
        )
        if asset_query and content_type not in SERVER_SIDE_QUERY_CONTENT_TYPES:
            raise ValueError(
                "selector.assetQuery is a server-side Cloud Asset query. "
                "It is only supported for contentType RESOURCE (searchAllResources) "
                "and IAM_POLICY (searchAllIamPolicies). "
                f"contentType {content_type} is read with listAssets, which has no query parameter. "
                "Remove assetQuery or change contentType."
            )
        return values


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
    function_url: str = Field(
        alias="functionUrl",
        title="Function URL",
        description="URL of the HTTP endpoint implementing the cloud-function sync protocol (e.g. a Cloud Run service).",
    )
    resource: str = Field(
        title="Resource",
        description="Resource name forwarded to the cloud function endpoint so it can route internally (e.g. 'employees').",
    )


class GCPCloudFunctionResourceConfig(ResourceConfig):
    kind: Literal["gcpCloudFunction"] = Field(
        title="GCP Cloud Function",
        description="GCP cloud-function sync protocol resource kind.",
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

    @root_validator(pre=True)
    def _validate_content_type_for_kind(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Reject selectors that would silently drop contentType or assetQuery."""
        resources = values.get("resources") or []
        if not isinstance(resources, list):
            return values
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            kind = resource.get("kind")
            selector = resource.get("selector") or {}
            if not isinstance(selector, dict):
                continue
            content_type_raw = selector.get("contentType", selector.get("content_type"))
            asset_query_raw = selector.get("assetQuery", selector.get("asset_query"))
            has_content_type_key = (
                "contentType" in selector or "content_type" in selector
            )
            has_asset_query = isinstance(asset_query_raw, str) and bool(
                asset_query_raw.strip()
            )
            if kind in NON_ASSET_KINDS and (has_content_type_key or has_asset_query):
                raise ValueError(
                    f"{kind} does not read Cloud Asset Inventory content types. "
                    "Remove selector.contentType and selector.assetQuery."
                )
            if kind not in RESOURCE_KINDS_WITHOUT_ASSET_QUERY or not has_asset_query:
                continue
            content_type = (
                content_type_raw.strip().upper()
                if isinstance(content_type_raw, str) and content_type_raw.strip()
                else CloudAssetContentType.RESOURCE.value
            )
            if content_type == CloudAssetContentType.RESOURCE:
                raise ValueError(
                    f"{kind} syncs RESOURCE data from its product API, not searchAllResources. "
                    "selector.assetQuery would be ignored. Remove assetQuery, or set contentType "
                    "to IAM_POLICY, ORG_POLICY, ACCESS_POLICY, OS_INVENTORY, or RELATIONSHIP "
                    "to read that content from Cloud Asset Inventory."
                )
        return values


class ProtoConfig(BaseModel):
    preserving_proto_field_name: bool | None = None
