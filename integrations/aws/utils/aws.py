from typing import Any, AsyncIterator, Optional, Union

import aioboto3
from starlette.requests import Request

from port_ocean.context.ocean import ocean
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from aws.aws_credentials import AwsCredentials
from aws.session_manager import SessionManager


_session_manager: SessionManager = SessionManager()


async def initialize_access_credentials() -> bool:
    await _session_manager.reset()
    return True


def describe_accessible_accounts() -> list[dict[str, Any]]:
    return _session_manager._aws_accessible_accounts


def get_default_region_from_credentials(
    credentials: AwsCredentials,
) -> Union[str, None]:
    return credentials.default_regions[0] if credentials.default_regions else None


async def get_accounts() -> AsyncIterator[AwsCredentials]:
    """
    Gets the AWS account IDs that the current IAM role can access.
    """

    for credentials in _session_manager._aws_credentials:
        yield credentials


async def session_factory(
    credentials: AwsCredentials,
    custom_region: Optional[str],
    use_default_region: Optional[bool],
) -> AsyncIterator[aioboto3.Session]:

    if use_default_region:
        default_region = get_default_region_from_credentials(credentials)
        yield await credentials.create_session(default_region)
    elif custom_region:
        yield await credentials.create_session(custom_region)
    else:
        async for session in credentials.create_session_for_each_region():
            yield session


async def get_sessions(
    custom_account_id: Optional[str] = None,
    custom_region: Optional[str] = None,
    use_default_region: Optional[bool] = None,
) -> AsyncIterator[aioboto3.Session]:
    """
    Gets boto3 sessions for the AWS regions.
    """

    if custom_account_id:
        credentials = _session_manager.find_credentials_by_account_id(custom_account_id)
        async for session in session_factory(
            credentials, custom_region, use_default_region
        ):
            yield session
    else:
        tasks = [
            session_factory(credentials, custom_region, use_default_region)
            async for credentials in get_accounts()
        ]
        if tasks:
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch


def validate_request(request: Request) -> tuple[bool, str]:
    api_key = request.headers.get("x-port-aws-ocean-api-key")
    if not api_key:
        return (False, "API key not found in request headers")
    if not ocean.integration_config.get("live_events_api_key"):
        return (False, "API key not found in integration config")
    if api_key != ocean.integration_config.get("live_events_api_key"):
        return (False, "Invalid API key")
    return (True, "Request validated")
