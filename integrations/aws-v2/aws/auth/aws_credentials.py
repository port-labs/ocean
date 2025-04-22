from typing import (
    AsyncIterator,
    Optional,
    Iterable,
    Dict,
    Any,
    Callable,
    Awaitable,
    List,
    Set,
    Tuple,
    cast,
)
import aioboto3
import asyncio
from aiobotocore.credentials import AioRefreshableCredentials
from aiobotocore.session import get_session
from datetime import datetime, timezone, timedelta
from loguru import logger
from functools import lru_cache
from types_aiobotocore_sts import STSClient
from port_ocean.context.ocean import ocean
from utils.misc import is_access_denied_exception
from overrides import AWSResourceConfig
from port_ocean.context.event import event


class RegionNotAllowedError(Exception):
    pass


class AwsCredentials:
    __slots__ = [
        "account_id",
        "role_arn",
        "session_name",
        "duration",
        "_enabled_regions",
        "default_credentials",
        "_session_cache",
    ]

    def __init__(
        self,
        account_id: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        role_arn: Optional[str] = None,
        session_name: Optional[str] = None,
        duration: Optional[float] = 3600,
    ):
        self.account_id = account_id
        self.role_arn = role_arn
        self.session_name = session_name
        self.duration = duration
        self.default_credentials: Dict[str, Any] = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
        }
        # Session caching
        self._session_cache: Dict[str, Tuple[aioboto3.Session, datetime]] = {}

    def is_role(self) -> bool:
        return bool(self.role_arn)

    def expiry_time(self) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.duration)
        return expiry.isoformat()

    async def get_enabled_regions(self) -> List[str]:
        """Get enabled regions from the account"""
        session = await self.create_session()
        async with session.client("account") as account_client:
            response = await account_client.list_regions(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
            )
            return response.get("Regions", [])

    def _create_refresh_function(self) -> Callable[[], Awaitable[Dict[str, Any]]]:
        """
        Returns a callable that fetches new credentials when the current credentials are close to expiry.
        """

        async def refresh() -> Dict[str, Any]:
            """
            Refreshes AWS credentials by re-assuming the role to get new credentials.
            :return: A dictionary containing the new credentials and their expiration time.
            """
            default_session = aioboto3.Session(**self.default_credentials)

            if self.is_role():
                logger.debug(
                    f"Refreshing AWS credentials for role {self.role_arn} in account {self.account_id}"
                )
                async with default_session.client("sts") as sts_client:
                    response = await sts_client.assume_role(
                        RoleArn=str(self.role_arn),
                        RoleSessionName=str(self.session_name),
                        DurationSeconds=int(self.duration),
                    )
                    credentials = response["Credentials"]

                    # Add buffer time to ensure credentials don't expire during use
                    expiry_time = (
                        credentials["Expiration"] - timedelta(minutes=5)
                    ).isoformat()

                    refreshable_credentials = {
                        "access_key": credentials["AccessKeyId"],
                        "secret_key": credentials["SecretAccessKey"],
                        "token": credentials["SessionToken"],
                        "expiry_time": expiry_time,
                    }
            else:
                logger.debug(
                    f"Using existing AWS credentials for default account {self.account_id}"
                )
                default_credentials = await default_session.get_credentials()  # type: ignore
                frozen_credentials = await default_credentials.get_frozen_credentials()

                refreshable_credentials = {
                    "access_key": frozen_credentials.access_key,
                    "secret_key": frozen_credentials.secret_key,
                    "token": frozen_credentials.token,
                    "expiry_time": self.expiry_time(),
                }
            return refreshable_credentials

        return refresh

    async def create_session(self, region: Optional[str] = None) -> aioboto3.Session:
        """
        Create or return a cached session with region support
        """
        cache_key = region or "default"

        # Check if we have a cached session that's still valid
        if cache_key in self._session_cache:
            session, expiry = self._session_cache[cache_key]
            # If session expires in more than 10 minutes, reuse it
            if expiry > datetime.now(timezone.utc) + timedelta(minutes=10):
                return session

        logger.debug(
            f"Creating new session for account {self.account_id}{f' in region {region}' if region else ''}"
        )

        refresh_func = self._create_refresh_function()

        credentials = AioRefreshableCredentials.create_from_metadata(
            metadata=await refresh_func(),
            refresh_using=refresh_func,
            method="sts-assume-role",
        )

        botocore_session = get_session()
        setattr(botocore_session, "_credentials", credentials)
        if region:
            botocore_session.set_config_variable("region", region)

        session = aioboto3.Session(botocore_session=botocore_session)

        # Cache the session with expiry time
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.duration - 300)
        self._session_cache[cache_key] = (session, expiry)

        return session

    async def is_region_allowed(self, region: str) -> bool:
        """Check if a region is allowed by the user"""
        aws_resource_config = cast(AWSResourceConfig, event.resource_config)
        allowed_regions = filter(
            aws_resource_config.selector.is_region_allowed, self.get_enabled_regions()
        )
        return region in allowed_regions

    async def allowed_regions(self) -> Set[str]:
        """Check if a region is allowed by the user"""
        aws_resource_config = cast(AWSResourceConfig, event.resource_config)
        allowed_regions = filter(
            aws_resource_config.selector.is_region_allowed, self.get_enabled_regions()
        )
        return set(allowed_regions)

    async def create_session_for_each_region(self) -> List[aioboto3.Session]:
        """
        Create sessions for multiple regions
        """
        regions = await self.allowed_regions()

        tasks = [self.create_session(region) for region in regions]
        sessions = await asyncio.gather(*tasks)
        return sessions

    async def create_session_for_each_region(self) -> AsyncIterator[aioboto3.Session]:
        """
        Create sessions for multiple regions
        """
        regions = await self.allowed_regions()
        for region in regions:
            session = await self.create_session(region)
            yield session
