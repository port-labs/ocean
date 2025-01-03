from typing import AsyncIterator, Optional, Iterable, Dict, Any, Callable, Awaitable
import typing
import aioboto3
from aiobotocore.credentials import (
    AioRefreshableCredentials,
)
from aiobotocore.session import get_session
from loguru import logger

from types_aiobotocore_sts import STSClient

from datetime import datetime, timezone, timedelta


class AwsCredentials:
    def __init__(
        self,
        account_id: str,
        access_key_id: Optional[str] = None,
        sts_client: Optional[STSClient] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        role_arn: Optional[str] = None,
        session_name: Optional[str] = None,
        duration: Optional[float] = None,
    ):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.enabled_regions: list[str] = []
        self.default_regions: list[str] = []
        self.role_arn = role_arn
        self.session_name = session_name
        self.session_token = session_token
        self.duration = duration
        self.sts_client = sts_client

    def is_role(self) -> bool:
        return self.role_arn is not None

    def expiry_time(self) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.duration or 3600)
        return expiry.isoformat()

    async def update_enabled_regions(self) -> None:
        session = await self.create_session()
        async with session.client("account") as account_client:
            response = await account_client.list_regions(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
            )
            regions = response.get("Regions", [])
            self.enabled_regions = [region["RegionName"] for region in regions]
            self.default_regions = [
                region["RegionName"]
                for region in regions
                if region["RegionOptStatus"] == "ENABLED_BY_DEFAULT"
            ]

    def _create_refresh_function(self) -> Callable[[], Awaitable[Dict[str, Any]]]:
        """
        Returns a callable that fetches new credentials when the current credentials are close to expiry.
        """

        async def refresh() -> Dict[str, Any]:
            """
            Refreshes AWS credentials by re-assuming the role to get new credentials.

            :return: A dictionary containing the new credentials and their expiration time.
            """
            sts_client = typing.cast(STSClient, self.sts_client)
            response = await sts_client.assume_role(
                RoleArn=str(self.role_arn),
                RoleSessionName=str(self.session_name),
            )
            credentials = response["Credentials"]
            self.access_key_id = credentials["AccessKeyId"]
            self.secret_access_key = credentials["SecretAccessKey"]
            self.session_token = credentials["SessionToken"]
            self.expiration = credentials["Expiration"].isoformat()
            return {
                "access_key": self.access_key_id,
                "secret_key": self.secret_access_key,
                "token": self.session_token,
                "expiry_time": self.expiration,
            }

        return refresh

    async def create_session(self, region: Optional[str] = None) -> aioboto3.Session:
        """
        Create a session possibly using AioRefreshableCredentials for auto refresh if these are role-based credentials.
        """
        if self.is_role():
            # For a role, use a refreshable credentials object
            logger.debug(
                f"Creating a refreshable session for role {self.role_arn} in account {self.account_id} for region {region}"
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

            autorefresh_session = aioboto3.Session(botocore_session=botocore_session)
            return autorefresh_session

        else:
            return aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=region,
            )

    async def create_session_for_each_region(
        self, allowed_regions: Optional[Iterable[str]] = None
    ) -> AsyncIterator[aioboto3.Session]:
        regions = allowed_regions or self.enabled_regions

        for region in regions:
            yield await self.create_session(region)
