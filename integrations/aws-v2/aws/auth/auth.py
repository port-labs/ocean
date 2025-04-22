from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import (
    AsyncIterator,
    Dict,
    Tuple,
    Optional,
    List,
    Any,
    Callable,
    Awaitable,
    Set,
    cast,
)

import aioboto3
from loguru import logger
from port_ocean.context.ocean import ocean
from utils.misc import is_access_denied_exception
from port_ocean.exceptions.core import OceanAbortException
from aws.auth.aws_credentials import AwsCredentials

__all__ = ("SessionManager",)


class AccountNotFoundError(OceanAbortException):
    """Raised when we cannot map a session back to an account ID."""


class SessionManager:
    """
    Memory‑lean session manager.

    * Stores **no** catalogue of accounts in RAM.
    * Yields each (account‑dict, AwsCredentials) or
      directly a Session as soon as it is verified.
    * Uses a bounded semaphore so at most `concurrency`
      role‑assume requests are in flight at once.
    """

    __slots__ = [
        "_application_credentials",
        "_application_session",
        "_organization_reader",
    ]

    def __init__(self) -> None:
        self._application_credentials: Optional[AwsCredentials] = None
        self._application_session: Optional[aioboto3.Session] = None
        self._organization_reader: Optional[aioboto3.Session] = None

    async def setup(self) -> None:
        """
        Initialise the application and (optionally) organization reader sessions.
        Nothing else is cached.
        """
        self._application_credentials = await self._get_application_credentials()
        self._application_session = await self._application_credentials.create_session()
        self._organization_reader = await self._get_organization_session()
        logger.info("SessionManager ready – organisation reader initialised.")

    async def iter_accessible_accounts(
        self, *, concurrency: int = 15
    ) -> AsyncIterator[Tuple[Dict[str, Any], AwsCredentials]]:
        """
        Yield `(account_info, AwsCredentials)` for every account
        in the organisation that we can successfully assume into.

        The application’s own account is always first.
        Nothing is cached; once the caller drops a credentials object
        it can be GC‑collected.
        """
        # 1️⃣  Application account → always accessible
        app_creds = cast(AwsCredentials, self._application_credentials)
        yield (
            {
                "Id": app_creds.account_id,
                "Name": "Application Account",
            },
            app_creds,
        )

        # 2️⃣  Organisation accounts → iterate + assume in a bounded pool
        org_reader = cast(aioboto3.Session, self._organization_reader)
        sem = asyncio.Semaphore(concurrency)

        async for page in self._get_organization_accounts(org_reader):
            if not page:  # empty page
                continue

            # spawn assume‑role tasks and consume them as they complete
            coros = [_AssumeTask(self, acc, sem).run() for acc in page]
            for fut in asyncio.as_completed(coros):
                result = await fut
                if result:  # None means assume failed
                    yield result

    def __get_default_keys(self) -> Dict[str, str | None]:
        return {
            "aws_access_key_id": ocean.integration_config.get("aws_access_key_id"),
            "aws_secret_access_key": ocean.integration_config.get(
                "aws_secret_access_key"
            ),
        }

    async def _get_application_credentials(self) -> AwsCredentials:
        keys = self.__get_default_keys()
        session = aioboto3.Session(**keys)
        async with session.client("sts") as sts:
            caller = await sts.get_caller_identity()

        return AwsCredentials(
            account_id=caller["Account"],
            access_key_id=keys["aws_access_key_id"],
            secret_access_key=keys["aws_secret_access_key"],
            duration=3600,
        )

    async def _get_organization_session(self) -> aioboto3.Session:
        """
        Return a session that can list organisation accounts, falling back to
        the application session if we cannot assume the org‑reader role.
        """
        org_role_arn = ocean.integration_config.get("organization_role_arn")
        app_session = cast(aioboto3.Session, self._application_session)

        if not org_role_arn:
            logger.warning(
                "No organisation reader role configured – using application session."
            )
            return app_session

        try:
            async with app_session.client("sts") as sts:
                creds = (
                    await sts.assume_role(
                        RoleArn=org_role_arn,
                        RoleSessionName="OceanOrgAssumeRoleSession",
                        DurationSeconds=3600,
                    )
                )["Credentials"]
            return aioboto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
            )
        except Exception as exc:
            if is_access_denied_exception(exc):
                logger.warning(
                    "Cannot assume organisation reader role – continuing with "
                    "application credentials."
                )
            else:
                logger.error(
                    f"Error assuming organisation reader role: {exc!s} – "
                    "continuing with application credentials."
                )
            return app_session

    async def _get_organization_accounts(
        self, session: aioboto3.Session
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream pages of `list_accounts()` without storing them."""
        async with session.client("organizations") as orgs:
            paginator = orgs.get_paginator("list_accounts")
            try:
                async for page in paginator.paginate():
                    yield page["Accounts"]
            except orgs.exceptions.AccessDeniedException:
                logger.warning(
                    "Caller not in an AWS Organisation – single‑account mode."
                )
            except orgs.exceptions.AWSOrganizationsNotInUseException:
                logger.warning("AWS Organisations not enabled – single‑account mode.")
            except Exception as exc:
                logger.warning(f"Could not enumerate organisation accounts: {exc!s}")

    async def find_account_id_by_session(self, session: aioboto3.Session) -> str:
        async with session.client("sts") as sts:
            return (await sts.get_caller_identity())["Account"]


class _AssumeTask:
    """
    One‑shot role‑assume wrapper that respects a global semaphore.
    Returns `(account_info, AwsCredentials)` on success or `None` on failure.
    """

    def __init__(
        self,
        mgr: SessionManager,
        account: Dict[str, Any],
        sem: asyncio.Semaphore,
    ) -> None:
        self._mgr = mgr
        self._account = account
        self._sem = sem

    async def run(self) -> Optional[Tuple[Dict[str, Any], AwsCredentials]]:
        async with self._sem:
            account_id = self._account["Id"]
            role_name = ocean.integration_config.get("account_read_role_name")
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
            session_name = "OceanMemberAssumeRoleSession"
            default_keys = self._mgr.__get_default_keys()

            app_session = cast(aioboto3.Session, self._mgr._application_session)
            try:
                # quick assume‑role sanity check
                async with app_session.client("sts") as sts:
                    await sts.assume_role(
                        RoleArn=role_arn,
                        RoleSessionName=session_name,
                        DurationSeconds=3600,
                    )

                creds = AwsCredentials(
                    account_id=account_id,
                    access_key_id=default_keys["aws_access_key_id"],
                    secret_access_key=default_keys["aws_secret_access_key"],
                    role_arn=role_arn,
                    session_name=session_name,
                    duration=3600,
                )
                return self._account, creds

            except Exception as exc:
                if is_access_denied_exception(exc):
                    logger.info(f"No permissions in account {account_id}; skipping")
                else:
                    logger.error(
                        f"Failed to assume role in account {account_id}: {exc!s}"
                    )
                return None
