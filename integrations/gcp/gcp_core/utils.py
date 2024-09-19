import enum
import base64
import os
import typing
from collections.abc import MutableSequence
from typing import Any, TypedDict, Tuple

from loguru import logger
import proto  # type: ignore
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from gcp_core.overrides import GCPCloudResourceConfig
from port_ocean.context.ocean import ocean
import json
from pathlib import Path
from gcp_core.helpers.ratelimiter.overrides import (
    SearchAllResourcesQpmPerProject,
    PubSubAdministratorPerMinutePerProject,
)

search_all_resources_qpm_per_project = SearchAllResourcesQpmPerProject()
pubsub_administrator_per_minute_per_project = PubSubAdministratorPerMinutePerProject()

EXTRA_PROJECT_FIELD = "__project"
DEFAULT_CREDENTIALS_FILE_PATH = (
    f"{Path.home()}/.config/gcloud/application_default_credentials.json"
)

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
    SUBSCRIPTION = "pubsub.googleapis.com/Subscription"
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
    credentials_json = ""
    if ocean.integration_config.get("encoded_adc_configuration"):
        b64_credentials = ocean.integration_config["encoded_adc_configuration"]
        credentials_json = base64.b64decode(b64_credentials).decode("utf-8")
    else:
        try:
            file_path: str = (
                os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                or DEFAULT_CREDENTIALS_FILE_PATH
            )
            with open(file_path, "r", encoding="utf-8") as file:
                credentials_json = file.read()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Couldn't find the google credentials file. Please set the GOOGLE_APPLICATION_CREDENTIALS environment variable properly. Error: {str(e)}"
            )
    return credentials_json


def get_service_account_project_id() -> str:
    "get project id associated with service account"
    try:
        default_credentials = json.loads(get_credentials_json())
        project_id = default_credentials.get("project_id") or default_credentials.get(
            "quota_project_id"
        )

        if not project_id:
            raise KeyError("project_id or quota_project_id")

        return project_id
    except FileNotFoundError as e:
        gcp_project_env = os.getenv("GCP_PROJECT")
        if isinstance(gcp_project_env, str):
            return gcp_project_env
        else:
            raise ValueError(
                f"Couldn't figure out the service account's project id. You can specify it using the GCP_PROJECT environment variable. Error: {str(e)}"
            )
    except KeyError as e:
        raise ValueError(
            f"Couldn't figure out the service account's project id. Key: {str(e)} doesn't exist in the credentials file."
        )
    except Exception as e:
        raise ValueError(
            f"Couldn't figure out the service account's project id. Error: {str(e)}"
        )
    raise ValueError("Couldn't figure out the service account's project id.")


async def get_quotas_for_project(
    project_id: str, kind: str
) -> Tuple["AsyncLimiter", "BoundedSemaphore"]:
    try:
        match kind:
            case (
                AssetTypesWithSpecialHandling.TOPIC
                | AssetTypesWithSpecialHandling.SUBSCRIPTION
            ):
                topic_rate_limiter = (
                    await pubsub_administrator_per_minute_per_project.limiter(
                        project_id
                    )
                )
                topic_semaphore = (
                    await pubsub_administrator_per_minute_per_project.semaphore(
                        project_id
                    )
                )
                return (topic_rate_limiter, topic_semaphore)
            case _:
                asset_rate_limiter = await search_all_resources_qpm_per_project.limiter(
                    project_id
                )
                asset_semaphore = await search_all_resources_qpm_per_project.semaphore(
                    project_id
                )
                return (asset_rate_limiter, asset_semaphore)
    except Exception as e:
        logger.warning(
            f"Failed to compute quota dynamically due to error. Will use default values. Error: {str(e)}"
        )
        default_rate_limiter = (
            await search_all_resources_qpm_per_project.default_rate_limiter()
        )
        default_semaphore = (
            await search_all_resources_qpm_per_project.default_semaphore()
        )
        return (default_rate_limiter, default_semaphore)


async def resolve_request_controllers(
    kind: str,
) -> Tuple["AsyncLimiter", "BoundedSemaphore"]:
    service_account_project_id = get_service_account_project_id()
    return await get_quotas_for_project(service_account_project_id, kind)
