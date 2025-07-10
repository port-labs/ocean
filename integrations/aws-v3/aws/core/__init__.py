"""
Core AWS functionality for the v3 integration.
"""

from aws.core.cloudcontrol_sync import (
    get_allowed_regions,
    resync_cloudcontrol,
    resync_resources_for_account_with_session,
)
from aws.core.paginator import AsyncPaginator
from aws.core.utils import (
    ASYNC_GENERATOR_RESYNC_TYPE,
    CloudControlClientProtocol,
    CloudControlThrottlingConfig,
    CustomProperties,
    RAW_ITEM,
    RAW_RESULT,
    fix_unserializable_date_properties,
    is_access_denied_exception,
    is_global_resource,
    is_resource_not_found_exception,
)

__all__ = [
    "get_allowed_regions",
    "resync_cloudcontrol",
    "resync_resources_for_account_with_session",
    "AsyncPaginator",
    "RAW_ITEM",
    "RAW_RESULT",
    "ASYNC_GENERATOR_RESYNC_TYPE",
    "CloudControlThrottlingConfig",
    "CloudControlClientProtocol",
    "CustomProperties",
    "is_access_denied_exception",
    "is_resource_not_found_exception",
    "is_global_resource",
    "fix_unserializable_date_properties",
]
