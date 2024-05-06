from typing import Any, AsyncIterator, Optional
import aioboto3
from loguru import logger
from aws.session_manager import SessionManager
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


_session_manager: SessionManager = SessionManager()


async def update_available_access_credentials() -> None:
    """
    Fetches the AWS account IDs that the current IAM role can access.
    and saves them up to use as sessions

    :return: List of AWS account IDs.
    """
    logger.info("Updating AWS credentials")
    await _session_manager.reset()


def describe_accessible_accounts() -> list[dict[str, Any]]:
    return _session_manager._aws_accessible_accounts


async def get_sessions(
    custom_account_id: Optional[str] = None,
    custom_region: Optional[str] = None,
    use_default_region: Optional[bool] = None,
) -> AsyncIterator[aioboto3.Session]:
    """
    Gets boto3 sessions for the AWS regions
    """
    if custom_account_id:
        credentials = _session_manager.find_credentials_by_account_id(custom_account_id)
        if use_default_region:
            yield await credentials.create_session()
        elif custom_region:
            yield await credentials.create_session(custom_region)
        else:
            async for session in credentials.create_session_for_each_region():
                yield await session
        return

    for credentials in _session_manager._aws_credentials:
        if use_default_region:
            yield await credentials.create_session()
        elif custom_region:
            yield await credentials.create_session(custom_region)
        else:
            async for session in credentials.create_session_for_each_region():
                yield await session


def validate_request(request: Request) -> tuple[bool, str]:
    api_key = request.headers.get("x-port-aws-ocean-api-key")
    if not api_key:
        return (False, "API key not found in request headers")
    if not ocean.integration_config.get("aws_real_time_updates_requests_api_key"):
        return (False, "API key not found in integration config")
    if api_key != ocean.integration_config.get(
        "aws_real_time_updates_requests_api_key"
    ):
        return (False, "Invalid API key")
    return (True, "Request validated")
