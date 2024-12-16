from typing import AsyncIterator, Optional, Iterable
import aioboto3
import datetime
from aiobotocore.credentials import AioRefreshableCredentials
from botocore.credentials import ReadOnlyCredentials


class AwsCredentials:
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: Optional[str] = None,
        expiry_time: Optional[datetime.datetime] = None,
    ):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.enabled_regions: list[str] = []
        self.default_regions: list[str] = []
        self.expiry_time = expiry_time or (datetime.datetime.utcnow() + datetime.timedelta(seconds=3600))

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

    async def create_session(self, region: Optional[str] = None) -> aioboto3.Session:
        """
        Create a session possibly using AioRefreshableCredentials for auto refresh if these are role-based credentials.
        """
        if self.is_role():
            # For a role, use a refreshable credentials object
            refresh_func = self._create_refresh_function()
            refreshable = AioRefreshableCredentials.create(
                refresh_func,
                'sts',
                'v4',
                time_fetcher=lambda: datetime.datetime.utcnow()
            )
            return aioboto3.Session(botocore_session=refreshable.session, region_name=region)
        else:
            return aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=region,
            )

    def _create_refresh_function(self):
        """
        Returns a callable that fetches new credentials when the current credentials are close to expiry.
        For simplicity, this function just returns the current credentials.
        In a real scenario, you'd re-assume the role or fetch fresh credentials here.
        """
        async def refresh():
            # In a real-world scenario, you'd call STS again to get fresh creds.
            # Here, we just return the same credentials for demonstration.
            return {
                'access_key': self.access_key_id,
                'secret_key': self.secret_access_key,
                'token': self.session_token,
                'expiry_time': (self.expiry_time.isoformat() if self.expiry_time else (datetime.datetime.utcnow() + datetime.timedelta(minutes=50)).isoformat())
            }
        return refresh

    async def create_session_for_each_region(
        self, allowed_regions: Optional[Iterable[str]] = None
    ) -> AsyncIterator[aioboto3.Session]:
        regions = allowed_regions or self.enabled_regions
        for region in regions:
            yield await self.create_session(region)
