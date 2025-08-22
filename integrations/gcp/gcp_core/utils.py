import enum
import base64
import os
import typing
from typing import List, Dict
from collections.abc import MutableSequence
from typing import Any, TypedDict, Tuple, Optional
from gcp_core.errors import ResourceNotFoundError
from loguru import logger
import proto  # type: ignore
from gcp_core.helpers.ratelimiter.base import PersistentAsyncLimiter
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from gcp_core.overrides import GCPCloudResourceConfig, ProtoConfig
from port_ocean.context.ocean import ocean
import json
from pathlib import Path
from aiolimiter import AsyncLimiter
from gcp_core.helpers.ratelimiter.overrides import (
    SearchAllResourcesQpmPerProject,
    PubSubAdministratorPerMinutePerProject,
    ProjectGetRequestsPerMinutePerProject,
)
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest
import asyncio
from port_ocean.utils.async_http import http_async_client
from httpx import HTTPError

search_all_resources_qpm_per_project = SearchAllResourcesQpmPerProject()
pubsub_administrator_per_minute_per_project = PubSubAdministratorPerMinutePerProject()
project_get_requests_per_minute_per_project = ProjectGetRequestsPerMinutePerProject()

EXTRA_PROJECT_FIELD = "__project"
DEFAULT_CREDENTIALS_FILE_PATH = (
    f"{Path.home()}/.config/gcloud/application_default_credentials.json"
)

CLOUD_QUOTAS_SCOPE = "https://www.googleapis.com/auth/cloud-platform.read-only"
CLOUD_QUOTAS_BASE_URL = "https://cloudquotas.googleapis.com/v1/"
_QUOTA_PERCENTAGE = 0.8
_INITIAL_QUOTA_MAX_RETRIES = 3
_INITIAL_QUOTA_TIMEOUT = 10.0

if typing.TYPE_CHECKING:
    from asyncio import BoundedSemaphore


class VersionedResource(TypedDict):
    version: int
    resource: dict[Any, Any]


class AssetData(TypedDict):
    versioned_resources: list[VersionedResource]


def parse_latest_resource_from_asset(asset_data: AssetData) -> dict[Any, Any]:
    """
    Parse the latest version of a resource from asset data.

    Attempts to find the versioned resources using either snake_case or camelCase key,
    as the input format depends on how the asset data was originally serialized.

    Args:
        asset_data: Asset data containing versioned resources

    Returns:
        dict: The most recent version of the resource

    Raises:
        ResourceNotFoundError: If neither versioned_resources nor versionedResources is found
    """
    # Try both key formats since we don't control the input format
    versioned_resources = asset_data.get("versioned_resources") or asset_data.get(
        "versionedResources"
    )
    if not isinstance(versioned_resources, list):
        raise ResourceNotFoundError(
            "Could not find versioned resources under either 'versioned_resources' or 'versionedResources'. "
            "Please ensure the asset data contains a list of versioned resources in the expected format."
        )

    # Ensure each item in the list is a VersionedResource
    versioned_resources = typing.cast(list[VersionedResource], versioned_resources)

    max_versioned_resource_data = max(versioned_resources, key=lambda x: x["version"])
    return max_versioned_resource_data["resource"]


def should_use_snake_case() -> bool:
    """
    Determines whether to use snake_case for field names based on preserve_api_response_case_style config.

    Returns:
        bool: True to use snake_case, False to preserve API's original case style
    """

    selector = get_current_resource_config().selector
    preserve_api_case = getattr(selector, "preserve_api_response_case_style", False)
    return not preserve_api_case


def parse_protobuf_message(
    message: proto.Message,
    config: Optional[ProtoConfig] = None,
) -> dict[str, Any]:
    """
    Parse protobuf message to dict, controlling field name case style.
    """
    if config and config.preserving_proto_field_name is not None:
        use_snake_case = not config.preserving_proto_field_name
        return proto.Message.to_dict(
            message, preserving_proto_field_name=use_snake_case
        )
    use_snake_case = should_use_snake_case()
    return proto.Message.to_dict(message, preserving_proto_field_name=use_snake_case)


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
    project_id: str,
    kind: str,
) -> Tuple["AsyncLimiter", "BoundedSemaphore"]:
    try:
        match kind:
            case AssetTypesWithSpecialHandling.PROJECT:
                project_rate_limiter = await project_get_requests_per_minute_per_project.persistent_rate_limiter(
                    project_id
                )
                project_semaphore = await project_get_requests_per_minute_per_project.semaphore_for_real_time_event(
                    project_id
                )
                return project_rate_limiter, project_semaphore
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
) -> Tuple[(AsyncLimiter | PersistentAsyncLimiter), "BoundedSemaphore"]:
    service_account_project_id = get_service_account_project_id()
    return await get_quotas_for_project(service_account_project_id, kind)


async def _get_oauth_token(scope: str = CLOUD_QUOTAS_SCOPE) -> str:
    """
    Get OAuth token for the given scope.
    """
    creds, _ = google_auth_default(scopes=[scope])
    if not creds.valid or creds.expired:
        await asyncio.to_thread(creds.refresh, GoogleAuthRequest())
    return str(creds.token)


async def fetch_quota_info_rest(
    name: str
) -> List[Dict[str, Any]]:
    """
    Fetch quota info from the REST API.
    """
    token = await _get_oauth_token()
    url = f"{CLOUD_QUOTAS_BASE_URL}{name}"
    headers = {"Authorization": f"Bearer {token}"}
    backoff = 1.0
    for _ in range(_INITIAL_QUOTA_MAX_RETRIES):
        try:
            response = await http_async_client.get(url, headers=headers, timeout=_INITIAL_QUOTA_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            dims = data.get("dimensionsInfos", [])
            return dims if isinstance(dims, list) else []
        except (HTTPError, Exception) as e:
            logger.error(f"[fetch_quota_info_rest] Error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 10.0)
            continue
    return []


async def get_initial_quota_for_project_via_rest() -> int:
    project_id = get_service_account_project_id()
    name = (
        f"projects/{project_id}/locations/global/services/"
        f"cloudresourcemanager.googleapis.com/quotaInfos/ProjectV3GetRequestsPerMinutePerProject"
    )
    dims = await fetch_quota_info_rest(name)
    logger.debug(f"[get_initial_quota_for_project_via_rest] dims: {dims}")
    if not dims:
        default_quota = int(
            ocean.integration_config.get("search_all_resources_per_minute_quota", 400)
        )
        logger.debug(f"[get_initial_quota_for_project_via_rest] no dims, using default_quota: {default_quota}")
        return max(int(default_quota * _QUOTA_PERCENTAGE), 1)

    least = min(dims, key=lambda info: int(info["details"]["value"]))
    value = int(least["details"]["value"])
    return max(int(round(value * _QUOTA_PERCENTAGE)), 1)
