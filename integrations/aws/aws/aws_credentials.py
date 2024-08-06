from typing import AsyncIterator, Optional
import aioboto3


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
        self,
    ) -> AsyncIterator[aioboto3.Session]:
        for region in self.enabled_regions:
            yield await self.create_session(region)
