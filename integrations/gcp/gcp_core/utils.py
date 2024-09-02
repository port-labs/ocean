import enum
import base64
import typing
from collections.abc import MutableSequence
from typing import Any, TypedDict, Tuple

import proto  # type: ignore
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from gcp_core.overrides import GCPCloudResourceConfig
from port_ocean.context.ocean import ocean
import json

from gcp_core.helpers.ratelimiter.overrides import (
    SearchAllResourcesQpmPerProject,
    PubSubAdministratorPerMinutePerProject,
)

search_all_resources_qpm_per_project = SearchAllResourcesQpmPerProject()
pubsub_administrator_per_minute_per_project = PubSubAdministratorPerMinutePerProject()
EXTRA_PROJECT_FIELD = "__project"

if typing.TYPE_CHECKING:
    from aiolimiter import AsyncLimiter
    from asyncio import BoundedSemaphore


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


def get_credentials_json() -> str:
    b64_credentials = ocean.integration_config["encoded_adc_configuration"]
    credentials_json = base64.b64decode(b64_credentials).decode("utf-8")
    return credentials_json


def get_service_account_project_id() -> str:
    "get project id associated with service account"
    default_credentials = json.loads(get_credentials_json())
    project_id = default_credentials["project_id"]
    return project_id


SERVICE_ACCOUNT_PROJECT_ID = get_service_account_project_id()


async def resolve_request_controllers(
    kind: str,
) -> Tuple["AsyncLimiter", "BoundedSemaphore"]:
    if kind == AssetTypesWithSpecialHandling.TOPIC:
        topic_rate_limiter = await pubsub_administrator_per_minute_per_project.limiter(
            SERVICE_ACCOUNT_PROJECT_ID
        )
        topic_semaphore = await pubsub_administrator_per_minute_per_project.semaphore(
            SERVICE_ACCOUNT_PROJECT_ID
        )
        return (topic_rate_limiter, topic_semaphore)

    asset_rate_limiter = await search_all_resources_qpm_per_project.limiter(
        SERVICE_ACCOUNT_PROJECT_ID
    )
    asset_semaphore = await search_all_resources_qpm_per_project.semaphore(
        SERVICE_ACCOUNT_PROJECT_ID
    )
    return (asset_rate_limiter, asset_semaphore)
