from typing import Any, AsyncIterator, Optional, Union

import aioboto3
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from starlette.requests import Request

from aws.session_manager import SessionManager
from aws.aws_credentials import AwsCredentials

_session_manager: SessionManager = SessionManager()


async def update_available_access_credentials() -> None:
    """
    Fetches the AWS account IDs that the current IAM role can access.
    and saves them up to use as sessions

    :return: List of AWS account IDs.
    """
    CACHE_KEY = "CREDENTIALS_CACHE"

    if CACHE_KEY in event.attributes:
        return

    logger.info("Updating AWS credentials")
    await _session_manager.reset()
    # makes this run once per resync
    event.attributes[CACHE_KEY] = True


def describe_accessible_accounts() -> list[dict[str, Any]]:
    return _session_manager._aws_accessible_accounts


def get_default_region_from_credentials(
    credentials: AwsCredentials,
) -> Union[str, None]:
    return credentials.default_regions[0] if credentials.default_regions else None


async def get_sessions(
    custom_account_id: Optional[str] = None,
    custom_region: Optional[str] = None,
    use_default_region: Optional[bool] = None,
) -> AsyncIterator[aioboto3.Session]:
    """
    Gets boto3 sessions for the AWS regions
    """
    await update_available_access_credentials()

    if custom_account_id:
        credentials = _session_manager.find_credentials_by_account_id(custom_account_id)
        if use_default_region:
            default_region = get_default_region_from_credentials(credentials)
            yield await credentials.create_session(default_region)
        elif custom_region:
            yield await credentials.create_session(custom_region)
        else:
            async for session in credentials.create_session_for_each_region():
                yield await session
        return

    for credentials in _session_manager._aws_credentials:
        if use_default_region:
            default_region = get_default_region_from_credentials(credentials)
            yield await credentials.create_session(default_region)
        elif custom_region:
            yield await credentials.create_session(custom_region)
        else:
            async for session in credentials.create_session_for_each_region():
                yield await session


def validate_request(request: Request) -> tuple[bool, str]:
    api_key = request.headers.get("x-port-aws-ocean-api-key")
    if not api_key:
        return (False, "API key not found in request headers")
    if not ocean.integration_config.get("live_events_api_key"):
        return (False, "API key not found in integration config")
    if api_key != ocean.integration_config.get("live_events_api_key"):
        return (False, "Invalid API key")
    return (True, "Request validated")
