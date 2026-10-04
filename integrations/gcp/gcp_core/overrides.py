from typing import Any, ClassVar, Literal


from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic.v1 import Field, BaseModel, root_validator, validator

IAM_POLICY_KIND = "iam.googleapis.com/Policy"


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


class GCPIAMPolicySelector(Selector):
    asset_types: list[str] = Field(
        alias="assetTypes",
        min_items=1,
        title="Asset Types",
        description=(
            "Asset types whose explicit IAM allow policies are read with "
            "<a target='_blank' href='https://cloud.google.com/asset-inventory/docs/reference/rest/v1/TopLevel/searchAllIamPolicies'>searchAllIamPolicies</a>. "
            "At least one type is required. An empty asset type list searches every supported type and, together with each binding member, can create a very large number of entities. "
            "Policies attached to project resources are read once per accessible project. "
            "Include cloudresourcemanager.googleapis.com/Folder or cloudresourcemanager.googleapis.com/Organization only to read the allow policy set directly on those folders or organizations. "
            "Example: cloudresourcemanager.googleapis.com/Project"
        ),
    )
    policy_query: str | None = Field(
        default=None,
        alias="policyQuery",
        title="Policy Query",
        description=(
            "Optional Cloud Asset Inventory query matched against each explicit allow-policy binding (principal, role, and condition). "
            "Only matching bindings are returned. "
            "Example: memberTypes:serviceAccount keeps Google service account principals. "
            "Leave empty to return every explicit binding on the selected asset types. "
            "This query does not call Policy Analyzer and does not include inherited access. "
            "See <a target='_blank' href='https://cloud.google.com/asset-inventory/docs/searching-iam-policies'>search query syntax</a>."
        ),
    )

    @validator("asset_types")
    def _strip_asset_types(cls, value: list[str]) -> list[str]:
        cleaned = [asset_type.strip() for asset_type in value]
        if any(not asset_type for asset_type in cleaned):
            raise ValueError("assetTypes entries must be non-empty strings")
        return cleaned

    @validator("policy_query")
    def _blank_policy_query_is_unset(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GCPIAMPolicyResourceConfig(ResourceConfig):
    kind: Literal["iam.googleapis.com/Policy"] = Field(
        title="GCP IAM Allow Policy",
        description=(
            "Explicit IAM allow-policy bindings from Cloud Asset Inventory searchAllIamPolicies. "
            "Each item is one binding member on one resource (role, member, and resource), not effective or inherited access."
        ),
    )
    selector: GCPIAMPolicySelector = Field(
        title="IAM Policy Selector",
        description="Selector for explicit IAM allow-policy bindings.",
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
        | GCPIAMPolicyResourceConfig
        | GCPResourceConfig
    ] = Field(
        title="Resources",
        description="Configuration of resources to be synchronized by this app.",
        default_factory=list,
    )  # type: ignore[assignment]

    @root_validator(pre=True)
    def _iam_policy_kind_requires_asset_types(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        """Reject an IAM policy mapping that would search every asset type.

        The generic resource config accepts any kind. Without this check, a
        mapping that omits assetTypes would fall through to that config and
        the resync would have no server-side scope.
        """
        resources = values.get("resources") or []
        if not isinstance(resources, list):
            return values
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            if resource.get("kind") != IAM_POLICY_KIND:
                continue
            selector = resource.get("selector") or {}
            if not isinstance(selector, dict):
                raise ValueError(
                    f"{IAM_POLICY_KIND} selector must be a mapping that includes assetTypes"
                )
            asset_types = selector.get("assetTypes", selector.get("asset_types"))
            if not isinstance(asset_types, list) or not asset_types:
                raise ValueError(
                    f"{IAM_POLICY_KIND} requires selector.assetTypes with at least one "
                    "asset type so a resync does not inventory every IAM allow policy"
                )
            if any(
                not isinstance(asset_type, str) or not asset_type.strip()
                for asset_type in asset_types
            ):
                raise ValueError(
                    f"{IAM_POLICY_KIND} selector.assetTypes must be a list of non-empty strings"
                )
        return values


class ProtoConfig(BaseModel):
    preserving_proto_field_name: bool | None = None
