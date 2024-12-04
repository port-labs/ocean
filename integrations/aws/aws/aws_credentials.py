from typing import AsyncIterator, Optional, Iterable, List, Dict, Any
import aioboto3
from aiobotocore.credentials import AioRefreshableCredentials
from aiobotocore.session import get_session
from types_aiobotocore_sts import STSClient

from functools import partial


ASSUME_ROLE_DURATION_SECONDS = 3600  # 1 hour


class AwsCredentials:
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: Optional[str] = None,
        role_arn: Optional[str] = None,
        session_name: Optional[str] = None,
    ):
        """
        Represents AWS credentials for an account, with support for automatic refreshing.

        :param account_id: AWS account ID.
        :param access_key_id: AWS access key ID.
        :param secret_access_key: AWS secret access key.
        :param session_token: AWS session token (for temporary credentials).
        :param role_arn: ARN of the role to assume for refreshing credentials.
        :param session_name: Name for the assumed role session.
        """
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.role_arn = role_arn
        self.session_name = session_name
        self.enabled_regions: List[str] = []
        self.default_regions: List[str] = []

    async def _refresh_credentials(self, sts_client: STSClient) -> Dict[str, Any]:
        """
        Refreshes AWS credentials by re-assuming the role to get new credentials.

        :return: A dictionary containing the new credentials and their expiration time.
        """
        response = await sts_client.assume_role(
            RoleArn=str(self.role_arn),
            RoleSessionName=str(self.session_name),
            DurationSeconds=ASSUME_ROLE_DURATION_SECONDS,
        )
        credentials = response["Credentials"]
        self.access_key_id = credentials["AccessKeyId"]
        self.secret_access_key = credentials["SecretAccessKey"]
        self.session_token = credentials["SessionToken"]
        expiry_time = credentials["Expiration"].isoformat()
        return {
            "access_key": self.access_key_id,
            "secret_key": self.secret_access_key,
            "token": self.session_token,
            "expiry_time": expiry_time,
        }

    async def create_refreshable_session(
        self, region: Optional[str] = None
    ) -> aioboto3.Session:
        """
        Creates an aioboto3 Session with refreshable credentials.

        :param region: AWS region for the session.
        :return: An aioboto3 Session object.
        """
        if self.is_role():
            session = aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                aws_session_token=self.session_token,
            )
            async with session.client("sts") as sts_client:
                initial_credentials = await self._refresh_credentials(sts_client)
                refresh_credentials = partial(self._refresh_credentials, sts_client)
                refreshable_credentials = (
                    AioRefreshableCredentials.create_from_metadata(
                        metadata=initial_credentials,
                        refresh_using=refresh_credentials,
                        method="sts-assume-role",
                    )
                )
                botocore_session = get_session()
                botocore_session._credentials = refreshable_credentials  # type: ignore
                if region:
                    botocore_session.set_config_variable("region", region)
                autorefresh_session = aioboto3.Session(
                    botocore_session=botocore_session
                )
                return autorefresh_session
        else:
            session = aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=region,
            )
            return session

    async def update_enabled_regions(self) -> None:
        """
        Updates the list of enabled regions for the AWS account.
        """
        session = await self.create_refreshable_session()
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

    async def create_refreshable_session_for_each_region(
        self, allowed_regions: Optional[Iterable[str]] = None
    ) -> AsyncIterator[aioboto3.Session]:
        """
        Creates refreshable sessions for each allowed or enabled region.

        :param allowed_regions: Iterable of region names to create sessions for.
        :yield: An aioboto3 Session for each region.
        """
        regions = allowed_regions or self.enabled_regions
        for region in regions:
            yield await self.create_refreshable_session(region)

    def is_role(self) -> bool:
        """
        Checks if the credentials are for an assumed role.
        :return: True if the credentials are for a role, False otherwise.
        """
        return bool(self.session_token and self.role_arn)
