from typing import Any
import typing
import aioboto3
from aws.aws_credentials import AwsCredentials
from port_ocean.context.ocean import ocean
from loguru import logger

from types_aiobotocore_sts import STSClient


class SessionManager:
    def __init__(self) -> None:
        self._aws_accessible_accounts: list[dict[str, Any]] = []
        self._aws_credentials: list[AwsCredentials] = []
        self._application_account_id: str = ""
        self._application_session: aioboto3.Session | None = None
        self._organization_reader: aioboto3.Session | None = None

    async def reset(self) -> None:
        application_credentials = await self._get_application_credentials()
        await application_credentials.update_enabled_regions()
        self._application_account_id = application_credentials.account_id
        self._application_session = await application_credentials.create_session()

        self._aws_credentials.append(application_credentials)
        self._aws_accessible_accounts.append(
            {"Id": self._application_account_id, "Name": "Current Account"}
        )

        self._organization_reader = await self._get_organization_session()
        await self._update_available_access_credentials()

    async def _get_application_credentials(self) -> AwsCredentials:
        aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
        aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
        if not aws_access_key_id or not aws_secret_access_key:
            logger.warning(
                "Did not specify AWS access key ID or secret access key, Trying to fetch credentials using boto"
            )

        credentials = {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        }

        default_session = aioboto3.Session(**credentials)
        async with default_session.client("sts") as sts_client:
            caller_identity = await sts_client.get_caller_identity()
            current_account_id = caller_identity["Account"]
            default_credentials = await default_session.get_credentials()  # type: ignore
            frozen_credentials = await default_credentials.get_frozen_credentials()
            return AwsCredentials(
                account_id=current_account_id,
                access_key_id=frozen_credentials.access_key,
                secret_access_key=frozen_credentials.secret_key,
                session_token=frozen_credentials.token,
            )

    async def _get_organization_session(self) -> aioboto3.Session | None:
        organization_role_arn = ocean.integration_config.get("organization_role_arn")
        if not organization_role_arn:
            logger.warning(
                "Did not specify organization role ARN, assuming application role has access to organization accounts."
            )
            return self._application_session

        application_session = typing.cast(aioboto3.Session, self._application_session)

        async with application_session.client("sts") as sts_client:
            organizations_client = await sts_client.assume_role(
                RoleArn=organization_role_arn, RoleSessionName="AssumeRoleSession"
            )

            credentials = organizations_client["Credentials"]
            organization_role_session = aioboto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )

            return organization_role_session

    def _get_account_read_role_name(self) -> str:
        return ocean.integration_config.get("account_read_role_name", "")

    async def _update_available_access_credentials(self) -> None:
        logger.info("Updating AWS credentials")
        if not self._application_session or not self._organization_reader:
            raise ValueError(
                "Application session or organization reader session not initialized yet"
            )

        async with (
            self._application_session.client("sts") as sts_client,
            self._organization_reader.client("organizations") as organizations_client,
        ):
            paginator = organizations_client.get_paginator("list_accounts")
            try:
                async for page in paginator.paginate():
                    for account in page["Accounts"]:
                        if account["Id"] == self._application_account_id:
                            # Skip the current account as it is already added
                            # Replace the Temp account details with the current account details
                            self._aws_accessible_accounts[0] = account
                            continue
                        await self._assume_role_and_update_credentials(
                            sts_client, account
                        )
            except organizations_client.exceptions.AccessDeniedException:
                logger.warning(
                    "Caller is not a member of an AWS organization. Assuming role in the current account."
                )
        logger.info(f"Found {len(self._aws_credentials)} AWS accounts")

    async def _assume_role_and_update_credentials(
        self, sts_client: STSClient, account: dict[str, Any]
    ) -> None:
        try:
            account_role = await sts_client.assume_role(
                RoleArn=f'arn:aws:iam::{account["Id"]}:role/{self._get_account_read_role_name()}',
                RoleSessionName="AssumeRoleSession",
            )
            raw_credentials = account_role["Credentials"]
            credentials = AwsCredentials(
                account_id=account["Id"],
                access_key_id=raw_credentials["AccessKeyId"],
                secret_access_key=raw_credentials["SecretAccessKey"],
                session_token=raw_credentials["SessionToken"],
            )
            await credentials.update_enabled_regions()
            self._aws_credentials.append(credentials)
            self._aws_accessible_accounts.append(account)
        except sts_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AccessDenied":
                logger.info(f"Cannot assume role in account {account['Id']}. Skipping.")
                pass  # Skip the account if assume_role fails due to permission issues or non-existent role
            else:
                raise

    async def find_account_id_by_session(self, session: aioboto3.Session) -> str:
        session_credentials = await session.get_credentials()  # type: ignore
        frozen_credentials = await session_credentials.get_frozen_credentials()
        for cred in self._aws_credentials:
            if cred.access_key_id == frozen_credentials.access_key:
                return cred.account_id
        raise ValueError(f"Cannot find credentials linked with this session {session}")

    def find_credentials_by_account_id(self, account_id: str) -> AwsCredentials:
        for cred in self._aws_credentials:
            if cred.account_id == account_id:
                return cred

        if len(self._aws_credentials) == 1:
            return self._aws_credentials[0]

        raise ValueError(
            f"Cannot find credentials linked with this account id {account_id}"
        )
