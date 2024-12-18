from typing import AsyncIterator, Optional, Iterable, Dict, Any, Callable, Awaitable
import aioboto3
from aiobotocore.credentials import (
    AioRefreshableCredentials,
)
from aiobotocore.session import get_session
from loguru import logger


class AwsCredentials:
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: Optional[str] = None,
        role_arn: Optional[str] = None,
        session_name: Optional[str] = None,
        expiry_time: Optional[str] = None,
    ):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.enabled_regions: list[str] = []
        self.default_regions: list[str] = []
        self.role_arn = role_arn
        self.session_name = session_name
        self.expiry_time = expiry_time

    def is_role(self) -> bool:
        return self.session_token is not None

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

    def _create_refresh_function(
        self, session: aioboto3.Session
    ) -> Callable[[], Awaitable[Dict[str, Any]]]:
        """
        Returns a callable that fetches new credentials when the current credentials are close to expiry.
        """

        async def refresh() -> Dict[str, Any]:
            """
            Refreshes AWS credentials by re-assuming the role to get new credentials.

            :return: A dictionary containing the new credentials and their expiration time.
            """
            async with session.client("sts") as sts_client:
                response = await sts_client.assume_role(
                    RoleArn=str(self.role_arn),
                    RoleSessionName=str(self.session_name),
                )
                credentials = response["Credentials"]
                self.access_key_id = credentials["AccessKeyId"]
                self.secret_access_key = credentials["SecretAccessKey"]
                self.session_token = credentials["SessionToken"]
                self.expiry_time = credentials["Expiration"].isoformat()
                return {
                    "access_key": self.access_key_id,
                    "secret_key": self.secret_access_key,
                    "token": self.session_token,
                    "expiry_time": self.expiry_time,
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

            session = aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                aws_session_token=self.session_token,
            )

            refresh_func = self._create_refresh_function(session)

            initial_creds = {
                "access_key": self.access_key_id,
                "secret_key": self.secret_access_key,
                "token": self.session_token,
                "expiry_time": self.expiry_time,
            }

            credentials = AioRefreshableCredentials.create_from_metadata(
                metadata=initial_creds,
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
