from typing import AsyncIterator, Optional, Iterable, Dict, Any, Callable, Awaitable
import aioboto3
from aiobotocore.credentials import (
    AioRefreshableCredentials,
)
from aiobotocore.session import get_session
from loguru import logger

from datetime import datetime, timezone, timedelta


class AwsCredentials:
    def __init__(
        self,
        account_id: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
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
        self.duration = duration or 3600
        self.default_credentials: Dict[str, Any] = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
        }  # non-dynamic default credentials

    def is_role(self) -> bool:
        return bool(self.role_arn)

    def expiry_time(self) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.duration)
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

                    expiry_time = (
                        credentials["Expiration"]
                        - timedelta(
                            minutes=5
                        )  # ensure credentials have enough time before expiry
                    ).isoformat()
                    refreshable_credentials = {
                        "access_key": credentials["AccessKeyId"],
                        "secret_key": credentials["SecretAccessKey"],
                        "token": credentials["SessionToken"],
                        "expiry_time": expiry_time,
                    }
            else:
                logger.debug(
                    f"Refreshing AWS credentials for default account {self.account_id}"
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
        Create a session possibly using AioRefreshableCredentials for auto refresh if these are role-based credentials.
        """
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

    async def create_session_for_each_region(
        self, allowed_regions: Optional[Iterable[str]] = None
    ) -> AsyncIterator[aioboto3.Session]:
        regions = allowed_regions or self.enabled_regions
        for region in regions:
            yield await self.create_session(region)
