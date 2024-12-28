import typing

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field, BaseModel


class GCPCloudResourceSelector(Selector):
    resource_kinds: list[str] = Field(alias="resourceKinds", min_items=1)


class GCPCloudResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: GCPCloudResourceSelector


class GCPResourceSelector(Selector):
    preserve_api_response_case_style: bool | None = Field(
        default=None,
        alias="preserveApiResponseCaseStyle",
        description=(
            "Controls whether to preserve the Google Cloud API's original field format instead of using protobuf's default snake case. "
            "When False (default): Uses protobuf's default snake_case format (existing behavior). "
            "When True: Preserves the specific API's original format (e.g., camelCase for PubSub). "
            "If not set, defaults to False to maintain existing behavior (snake_case for all APIs)."
            "Note that this setting does not affect resources fetched from the cloud asset API"
        ),
    )


class GCPResourceConfig(ResourceConfig):
    selector: GCPResourceSelector


class GCPPortAppConfig(PortAppConfig):
    resources: list[GCPCloudResourceConfig | GCPResourceConfig | ResourceConfig] = (
        Field(default_factory=list)
    )


class ProtoConfig(BaseModel):
    preserving_proto_field_name: typing.Optional[bool] = None
