import enum
import typing
from collections.abc import MutableSequence
from typing import Any, TypedDict

import proto  # type: ignore
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from gcp_core.overrides import GCPCloudResourceConfig

EXTRA_PROJECT_FIELD = "__project"


class VersionedResource(TypedDict):
    version: int
    resource: dict[Any, Any]


class AssetData(TypedDict):
    versioned_resources: list[VersionedResource]


def parse_latest_resource_from_asset(asset_data: AssetData) -> dict[Any, Any]:
    max_versioned_resource_data = max(
        asset_data["versioned_resources"], key=lambda x: x["version"]
    )
    return max_versioned_resource_data["resource"]


def parse_protobuf_message(message: proto.Message) -> dict[str, Any]:
    return proto.Message.to_dict(message)


def parse_protobuf_messages(
    messages: MutableSequence[proto.Message],
) -> list[dict[str, Any]]:
    return [parse_protobuf_message(message) for message in messages]


class AssetTypesWithSpecialHandling(enum.StrEnum):
    TOPIC = "pubsub.googleapis.com/Topic"
    PROJECT = "cloudresourcemanager.googleapis.com/Project"
    ORGANIZATION = "cloudresourcemanager.googleapis.com/Organization"
    FOLDER = "cloudresourcemanager.googleapis.com/Folder"
    CLOUD_RESOURCE = "cloudResource"


def get_current_resource_config() -> (
    typing.Union[ResourceConfig, GCPCloudResourceConfig]
):
    """
    Returns the current resource config, accessible only inside an event context
    """
    return typing.cast(
        typing.Union[ResourceConfig, GCPCloudResourceConfig], event.resource_config
    )
