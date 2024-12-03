from typing import AsyncIterator, Optional, Iterable
import aioboto3

from aiobotocore.credentials import AioRefreshableCredentials
from aiobotocore.session import get_session

from datetime import datetime, timedelta
from time import time

TTL = 900


class AwsCredentials:
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: Optional[str] = None,
    ):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.enabled_regions: list[str] = []
        self.default_regions: list[str] = []

    async def update_enabled_regions(self) -> None:
        session = aioboto3.Session(
            self.access_key_id, self.secret_access_key, self.session_token
        )
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

    async def __get_session_credentials(self) -> dict:
            return {
                "access_key": self.access_key_id,
                "secret_key": self.secret_access_key,
                "token": self.session_token,
                "expiry_time": (datetime.now() + timedelta(seconds=TTL))
            }


    async def create_refreshable_session(self, region:str) -> aioboto3.Session:
        """
        Get refreshable aioboto3 session.
        """
        try:
            # get refreshable credentials
            refreshable_credentials = AioRefreshableCredentials.create_from_metadata(
                metadata=await self.__get_session_credentials(),
                refresh_using = self.__get_session_credentials,
                method="sts-assume-role",
            )

            # attach refreshable credentials current session
            session = get_session()
            session._credentials = refreshable_credentials
            session.set_config_variable("region", region)
            autorefresh_session = aioboto3.Session(botocore_session=session)

            return autorefresh_session

        except Exception as e:
            print(f"Error creating refreshable session: {e}")
            return aioboto3.Session()

    async def create_refreshable_session_for_each_region(
        self, allowed_regions: Optional[Iterable[str]] = None
    ) -> AsyncIterator[aioboto3.Session]:
        regions = allowed_regions or self.enabled_regions
        for region in regions:
            self.region_name = region
            yield await self.create_refreshable_session(region)

    def is_role(self) -> bool:
        return self.session_token is not None

    async def create_session(self, region: Optional[str] = None) -> aioboto3.Session:
        if self.is_role():
            return aioboto3.Session(
                self.access_key_id, self.secret_access_key, self.session_token, region
            )
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
