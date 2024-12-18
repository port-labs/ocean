from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from aws.aws_credentials import AwsCredentials
import aioboto3
from port_ocean.context.ocean import ocean
from loguru import logger
from types_aiobotocore_sts import STSClient
from utils.misc import is_access_denied_exception
from datetime import datetime, timezone, timedelta

ASSUME_ROLE_DURATION_SECONDS = 3600


class CredentialsProvider(ABC):
    @abstractmethod
    async def get_application_credentials(self) -> AwsCredentials:
        pass

    @abstractmethod
    async def get_all_accessible_accounts(
        self, application_session: aioboto3.Session
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of all accessible AWS accounts as dictionaries with 'Id' and 'Name'.
        """
        pass

    @abstractmethod
    async def get_account_credentials(
        self, sts_client: STSClient, account: Dict[str, Any]
    ) -> Optional[AwsCredentials]:
        """
        Assume a role in the given account and return the credentials.
        """
        pass

    def expiry_time(self) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(
            seconds=ASSUME_ROLE_DURATION_SECONDS
        )
        return expiry.isoformat()


class ApplicationCredentialsProvider(CredentialsProvider):
    async def get_application_credentials(self) -> AwsCredentials:
        aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
        aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
        if not aws_access_key_id or not aws_secret_access_key:
            logger.warning(
                "No AWS access key ID or secret access key provided, trying to fetch credentials using default boto chain."
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

    async def get_all_accessible_accounts(
        self, application_session: aioboto3.Session
    ) -> List[Dict[str, Any]]:
        # For just the application creds provider, we only return the current account
        async with application_session.client("sts") as sts_client:
            caller_identity = await sts_client.get_caller_identity()
            return [{"Id": caller_identity["Account"], "Name": "No name found"}]

    async def get_account_credentials(
        self, sts_client: STSClient, account: Dict[str, Any]
    ) -> Optional[AwsCredentials]:
        # For application-only scenario, there's no cross-account role assumption.
        # Just return the application credentials again if needed.
        raise NotImplementedError(
            "No cross-account assumption for application-only scenario."
        )


class OrganizationCredentialsProvider(ApplicationCredentialsProvider):
    def _get_organization_role_arn(self) -> str:
        return ocean.integration_config.get("organization_role_arn", "")

    def _get_account_read_role_name(self) -> str:
        return ocean.integration_config.get("account_read_role_name", "")

    async def get_organization_session(
        self, application_session: aioboto3.Session
    ) -> aioboto3.Session:
        organization_role_arn = self._get_organization_role_arn()
        role_session_name = "OceanOrgAssumeRoleSession"

        if not organization_role_arn:
            logger.warning(
                "No organization role ARN specified, assuming application role has access."
            )
            return application_session

        async with application_session.client("sts") as sts_client:
            try:
                org_response = await sts_client.assume_role(
                    RoleArn=organization_role_arn,
                    RoleSessionName=role_session_name,
                    DurationSeconds=ASSUME_ROLE_DURATION_SECONDS,
                )
                credentials = org_response["Credentials"]
                return aioboto3.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
            except sts_client.exceptions.ClientError as e:
                if is_access_denied_exception(e):
                    logger.warning(
                        "Cannot assume role to the organization account, using the application role."
                    )
                    return application_session
                else:
                    raise

    async def get_all_accessible_accounts(
        self, application_session: aioboto3.Session
    ) -> List[Dict[str, Any]]:
        organization_session = await self.get_organization_session(application_session)
        accounts = []
        async with organization_session.client("organizations") as organizations_client:
            paginator = organizations_client.get_paginator("list_accounts")
            try:
                async for page in paginator.paginate():
                    accounts.extend(page["Accounts"])
            except organizations_client.exceptions.AccessDeniedException:
                logger.warning(
                    "Caller is not a member of an AWS organization. Only the application account is accessible."
                )
                # Fallback to just application credentials if org isn't accessible
                async with application_session.client("sts") as sts_client:
                    caller_identity = await sts_client.get_caller_identity()
                    application_account_id = caller_identity["Account"]
                    logger.debug(
                        f"Using application account {application_account_id} as fallback."
                    )

                return [{"Id": application_account_id, "Name": "No name found"}]
        logger.info(f"Found {len(accounts)} AWS accounts in the organization.")
        return accounts

    async def get_account_credentials(
        self, sts_client: STSClient, account: Dict[str, Any]
    ) -> Optional[AwsCredentials]:
        role_arn = (
            f"arn:aws:iam::{account['Id']}:role/{self._get_account_read_role_name()}"
        )
        session_name = "OceanMemberAssumeRoleSession"

        try:
            account_role = await sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                DurationSeconds=ASSUME_ROLE_DURATION_SECONDS,
            )
            raw_credentials = account_role["Credentials"]
            return AwsCredentials(
                account_id=account["Id"],
                access_key_id=raw_credentials["AccessKeyId"],
                secret_access_key=raw_credentials["SecretAccessKey"],
                session_token=raw_credentials["SessionToken"],
                role_arn=role_arn,
                session_name=session_name,
                expiry_time=self.expiry_time(),
            )
        except sts_client.exceptions.ClientError as e:
            if is_access_denied_exception(e):
                logger.info(f"Cannot assume role in account {account['Id']}. Skipping.")
                return None
            else:
                raise
