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
from aws.auth.aws_credentials import AwsCredentials
from utils.misc import is_access_denied_exception
from port_ocean.exceptions.core import OceanAbortException


class AccountNotFoundError(OceanAbortException):
    pass


class SessionManager:
    __slots__ = [
        "_aws_accessible_accounts",
        "_aws_credentials",
        "_application_account_id",
        "_application_session",
        "_organization_reader",
    ]

    def __init__(self) -> None:
        """
        Optimized session manager with efficient memory usage and caching
        """
        self._aws_accessible_accounts: Dict[str, Dict[str, Any]] = {}
        self._aws_credentials: Dict[str, AwsCredentials] = {}
        self._application_account_id: str = ""
        self._application_session: Optional[aioboto3.Session] = None
        self._organization_reader: Optional[aioboto3.Session] = None

    async def setup(self) -> None:
        # Clear existing data
        self._aws_accessible_accounts = {}
        self._aws_credentials = {}

        # Get application credentials
        application_credentials = await self._get_application_credentials()
        self._application_account_id = application_credentials.account_id
        self._application_session = await application_credentials.create_session()

        # Store application credentials
        self._aws_credentials[self._application_account_id] = application_credentials
        self._aws_accessible_accounts[self._application_account_id] = {
            "Id": self._application_account_id,
            "Name": "Application Account",
        }

        # Set up organization reader and update account access
        self._organization_reader = await self._get_organization_session()
        await self._update_available_access_credentials()

        logger.info(
            f"Credentials updated. Found {len(self._aws_credentials)} AWS accounts"
        )

    def __get_default_keys(self) -> dict[str, Any]:
        return {
            "aws_access_key_id": ocean.integration_config.get("aws_access_key_id"),
            "aws_secret_access_key": ocean.integration_config.get(
                "aws_secret_access_key"
            ),
        }

    async def _get_application_credentials(self) -> AwsCredentials:
        credentials = self.__get_default_keys()
        aws_access_key_id = credentials["aws_access_key_id"]
        aws_secret_access_key = credentials["aws_secret_access_key"]

        if not aws_access_key_id or not aws_secret_access_key:
            logger.warning(
                "AWS credentials not specified, trying to fetch integration account credentials using boto"
            )

        default_session = aioboto3.Session(**credentials)
        async with default_session.client("sts") as sts_client:
            caller_identity = await sts_client.get_caller_identity()
            current_account_id = caller_identity["Account"]
            return AwsCredentials(
                account_id=current_account_id,
                access_key_id=aws_access_key_id,
                secret_access_key=aws_secret_access_key,
                duration=3600,  # 1 hour
            )

    async def _get_organization_session(self) -> aioboto3.Session:
        """Get organization session with better error handling"""

        organization_role_arn = ocean.integration_config.get("organization_role_arn")
        if not organization_role_arn:
            logger.warning(
                "No organization role ARN specified, assuming application has access to organization accounts."
            )
            return cast(aioboto3.Session, self._application_session)

        app_session = cast(aioboto3.Session, self._application_session)

        try:
            async with app_session.client("sts") as sts_client:
                response = await sts_client.assume_role(
                    RoleArn=organization_role_arn,
                    RoleSessionName="OceanOrgAssumeRoleSession",
                    DurationSeconds=3600,
                )

                credentials = response["Credentials"]
                return aioboto3.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
        except Exception as e:
            if is_access_denied_exception(e):
                logger.warning(
                    "Unable to assume organization role. This could be due to missing or incorrect trust relationships. "
                    "Continuing with application role permissions."
                )
            else:
                logger.error(
                    f"An error occurred while assuming organization role: {str(e)}, using application role"
                )
            return app_session

    @property
    def _account_read_role_name(self) -> str:
        return ocean.integration_config.get("account_read_role_name")

    async def _update_available_access_credentials(self) -> None:
        """Update credentials with parallel processing for better performance"""
        logger.info("Updating AWS credentials")
        org_reader = cast(aioboto3.Session, self._organization_reader)

        exceptions = []
        # Get all accounts in parallel
        async for accounts in self._get_organization_accounts(org_reader):
            # Process accounts in parallel
            if accounts:
                # Create tasks for all accounts that need processing
                tasks = {self._process_account(account) for account in accounts}

                if tasks:
                    errors = await asyncio.gather(*tasks, return_exceptions=True)
                    exceptions.extend(errors)
                tasks.clear()

        if exceptions:
            logger.info(
                f"Could not assume role in {len(exceptions)} accounts. To ingest resources from these accounts, ensure that each account has the role '{self._account_read_role_name}', is a member of the organization, and trusts the integration account."
            )

        logger.info(
            f"Successfully assumed role in {len(self._aws_credentials)} accounts"
        )

    async def _get_organization_accounts(
        self, session: aioboto3.Session
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Get all organization accounts with pagination support"""
        try:
            async with session.client("organizations") as organizations_client:
                paginator = organizations_client.get_paginator("list_accounts")
                async for page in paginator.paginate():
                    yield page["Accounts"]

        except organizations_client.exceptions.AccessDeniedException:
            logger.warning(
                "Caller is not a member of an AWS organization. Assuming role in the current account."
            )
        except organizations_client.exceptions.AWSOrganizationsNotInUseException:
            logger.warning(
                "AWS Organizations is not enabled in the current account. Assuming role in the current account."
            )
        except Exception as e:
            logger.warning(
                f"Failed to discover accessible organization accounts: {str(e)}"
            )

    async def _process_account(self, account: Dict[str, Any]) -> None:
        """Process a single account with role assumption"""

        account_id = account["Id"]
        try:
            role_arn = f"arn:aws:iam::{account_id}:role/{self._account_read_role_name}"
            session_name = "OceanMemberAssumeRoleSession"
            default_keys = self.__get_default_keys()

            # First check if we can assume the role without creating full credential object
            app_session = cast(aioboto3.Session, self._application_session)
            async with app_session.client("sts") as sts_client:
                # Just verify role assumption works
                await sts_client.assume_role(
                    RoleArn=role_arn, RoleSessionName=session_name, DurationSeconds=3600
                )

            # Only if assumption works, create full credentials object
            credentials = AwsCredentials(
                account_id=account_id,
                access_key_id=default_keys["aws_access_key_id"],
                secret_access_key=default_keys["aws_secret_access_key"],
                role_arn=role_arn,
                session_name=session_name,
                duration=3600,
            )

            # Store credentials without updating regions yet (lazy load later)
            self._aws_credentials[account_id] = credentials
            self._aws_accessible_accounts[account_id] = account

        except Exception as e:
            if is_access_denied_exception(e):
                logger.info(f"Cannot assume role in account {account_id}, Skipping...")
                pass  # Skip the account if assume_role fails due to permission issues or non-existent role
            else:
                logger.error(
                    f"An error occurred while assuming role in account {account_id}: {str(e)}"
                )
            raise

    async def find_account_id_by_session(self, session: aioboto3.Session) -> str:
        """Find account ID by session with caching"""
        # Check if account ID is cached in the session's identity
        async with session.client("sts") as sts_client:
            caller_identity = await sts_client.get_caller_identity()
            account_id = caller_identity["Account"]

            if account_id in self._aws_credentials:
                return account_id

        raise AccountNotFoundError(
            f"Cannot find credentials linked with this session in {session.region_name} region"
        )

    def find_credentials_by_account_id(self, account_id: str) -> AwsCredentials:
        """Find credentials by account ID with fallback for single account setup"""
        if account_id in self._aws_credentials:
            return self._aws_credentials[account_id]

        # For single account setups, return the application credentials
        if len(self._aws_credentials) == 1:
            return next(iter(self._aws_credentials.values()))

        raise AccountNotFoundError(f"Cannot find credentials for account {account_id}")
