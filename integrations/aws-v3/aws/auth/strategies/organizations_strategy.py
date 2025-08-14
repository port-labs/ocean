from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
from aws.auth.utils import AWSSessionError, extract_account_from_arn
from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from loguru import logger
import asyncio
from typing import Any, AsyncIterator, Dict, List
from botocore.utils import ArnParser


class OrganizationsHealthCheckMixin(AWSSessionStrategy, HealthCheckMixin):
    """Mixin for organizations health checking with batching and concurrency."""

    DEFAULT_CONCURRENCY = 10
    DEFAULT_BATCH_SIZE = 10

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

        self._organization_role_name: str | None = None
        self._valid_arns: list[str] = []
        self._valid_sessions: dict[str, AioSession] = {}
        self._organization_session: AioSession | None = None
        self._discovered_accounts: List[Dict[str, str]] = []

    @property
    def valid_arns(self) -> list[str]:
        """Get the list of valid ARNs that passed health check."""
        return getattr(self, "_valid_arns", [])

    def _get_organization_account_role_arn(self) -> str:
        """Get the organization account role ARN from the configuration."""
        account_role_arn: list[str] | None = self.config.get("account_role_arn")
        if (
            not account_role_arn
            or not isinstance(account_role_arn, list)
            or len(account_role_arn) == 0
        ):
            raise AWSSessionError(
                "account_role_arn is required and must be a non-empty list"
            )

        return account_role_arn[0]

    def _get_organization_account_role_name(self) -> str:
        """Get the account role ARN from the configuration."""
        if self._organization_role_name:
            return self._organization_role_name

        organization_role_arn = self._get_organization_account_role_arn()

        # validate role arn format
        if not organization_role_arn.startswith("arn:aws:iam::"):
            raise AWSSessionError("account_role_arn must be a valid ARN")

        arn_data = ArnParser().parse_arn(arn=organization_role_arn)
        if not isinstance(arn_data["resource"], str):
            raise AWSSessionError("account_role_arn must be a valid ARN")

        self._organization_role_name = arn_data["resource"]
        return self._organization_role_name

    def _build_role_arn(self, account_id: str) -> str:
        """Build the role ARN for the organization account."""
        role_name = self._get_organization_account_role_name()
        return f"arn:aws:iam::{account_id}:role/{role_name}"

    async def _get_organization_session(self) -> AioSession:
        """Get or create the organization session for the management account."""
        if self._organization_session:
            return self._organization_session

        organization_role_name = self._get_organization_account_role_name()
        logger.info(f"Assuming organization role: {organization_role_name}")

        organization_role_arn = self._get_organization_account_role_arn()
        try:
            session_kwargs = {
                "role_arn": organization_role_arn,
                "role_session_name": "OceanOrgAssumeRoleSession",
                "region": self.config.get("region"),
            }
            if self.config.get("external_id"):
                session_kwargs["external_id"] = self.config["external_id"]

            self._organization_session = await self.provider.get_session(
                **session_kwargs
            )
            logger.info("Successfully created organization session")
            return self._organization_session
        except Exception as e:
            logger.error(f"Failed to assume organization role: {e}")
            raise AWSSessionError(f"Cannot assume organization role: {e}")

    async def _discover_accounts(self) -> List[Dict[str, str]]:
        """Discover all accounts in the AWS Organization."""
        if self._discovered_accounts:
            return self._discovered_accounts

        organization_session = await self._get_organization_session()
        discovered_accounts = []

        try:
            async with organization_session.create_client(
                "organizations"
            ) as org_client:
                logger.info("Discovering accounts via AWS Organizations API")

                paginator = org_client.get_paginator("list_accounts")
                async for page in paginator.paginate():
                    for account in page["Accounts"]:
                        # Only include active accounts
                        if account["Status"] == "ACTIVE":
                            discovered_accounts.append(
                                {
                                    "Id": account["Id"],
                                    "Name": account["Name"],
                                    "Email": account.get("Email", ""),
                                    "Arn": account.get("Arn", ""),
                                }
                            )

                logger.info(f"Discovered {len(discovered_accounts)} active accounts")
                self._discovered_accounts = discovered_accounts
                return discovered_accounts

        except Exception as e:
            if "AccessDenied" in str(e):
                logger.warning("Access denied to AWS Organizations API")
                raise AWSSessionError(
                    "Cannot access AWS Organizations API - check permissions"
                )
            elif "AWSOrganizationsNotInUse" in str(e):
                logger.warning("AWS Organizations is not enabled in this account")
                raise AWSSessionError(
                    "AWS Organizations is not enabled in this account"
                )
            else:
                logger.error(f"Error discovering accounts: {e}")
                raise AWSSessionError(f"Failed to discover accounts: {e}")

    async def _can_assume_role_in_account(self, account_id: str) -> AioSession | None:
        """Check if we can assume the specified role in a given account."""
        role_arn = self._build_role_arn(account_id)

        try:
            session_kwargs = {
                "role_arn": role_arn,
                "role_session_name": "OceanMemberAssumeRoleSession",
                "region": self.config.get("region"),
            }
            if self.config.get("external_id"):
                session_kwargs["external_id"] = self.config["external_id"]

            session = await self.provider.get_session(**session_kwargs)
            logger.debug(
                f"Successfully assumed role '{role_arn}' in account {account_id}"
            )
            return session
        except Exception as e:
            logger.debug(
                f"Cannot assume role '{role_arn}' in account {account_id}: {e}"
            )
            return None

    async def healthcheck(self) -> bool:
        """Perform health check by discovering accounts and validating role assumption."""
        try:
            # Discover accounts first
            accounts = await self._discover_accounts()
            if not accounts:
                logger.warning("No accounts discovered in the organization")
                return False

            logger.info(
                f"Starting health check for {len(accounts)} discovered accounts"
            )

            # Validate role assumption for each account
            semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

            async def check_account(
                account: Dict[str, str],
            ) -> tuple[str, AioSession | None]:
                async with semaphore:
                    session = await self._can_assume_role_in_account(account["Id"])
                    return account["Id"], session

            # Process accounts in batches
            total_batches = (
                len(accounts) + self.DEFAULT_BATCH_SIZE - 1
            ) // self.DEFAULT_BATCH_SIZE

            for batch_num, batch_start in enumerate(
                range(0, len(accounts), self.DEFAULT_BATCH_SIZE), 1
            ):
                batch = accounts[batch_start : batch_start + self.DEFAULT_BATCH_SIZE]
                logger.debug(
                    f"Processing batch {batch_num}/{total_batches} ({len(batch)} accounts)"
                )

                tasks = [check_account(account) for account in batch]
                successful = 0

                for account, task in zip(batch, tasks):
                    try:
                        account_id, session = await task
                        if session:
                            role_arn = self._build_role_arn(account_id)
                            self._valid_arns.append(role_arn)
                            self._valid_sessions[role_arn] = session
                            successful += 1
                            logger.debug(
                                f"Role '{role_arn}' assumption validated for account {account_id}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Health check failed for account {account['Id']}: {e}"
                        )

                logger.debug(
                    f"Batch {batch_num}/{total_batches}: {successful}/{len(batch)} accounts validated"
                )
            logger.info(
                f"Health check complete: {len(self._valid_arns)}/{len(accounts)} accounts accessible"
            )

            if not self._valid_arns:
                raise AWSSessionError("No accounts are accessible after health check")

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise AWSSessionError(f"Organizations health check failed: {e}")


class OrganizationsStrategy(OrganizationsHealthCheckMixin):
    """
    Strategy for discovering AWS accounts via Organizations API and assuming roles in sub-accounts.

    This strategy:
    1. Assumes the organization role in the management account
    2. Uses AWS Organizations API to discover all accounts
    3. Attempts to assume the specified role in each discovered account
    4. Provides sessions for all accessible accounts
    """

    async def get_account_sessions(
        self, **kwargs: Any
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
        """Get sessions for all accessible accounts."""
        if not (self._valid_arns and self._valid_sessions):
            await self.healthcheck()

        if not (self._valid_arns and self._valid_sessions):
            raise AWSSessionError(
                "Account sessions not initialized. Run healthcheck first."
            )

        logger.info(f"Providing {len(self._valid_arns)} pre-validated AWS sessions")

        # Map role ARNs back to account information
        account_map = {account["Id"]: account for account in self._discovered_accounts}

        for role_arn in self._valid_arns:
            session = self._valid_sessions[role_arn]
            account_id = extract_account_from_arn(role_arn)

            # Get account info from discovered accounts
            account_info = account_map.get(
                account_id,
                {
                    "Id": account_id,
                    "Name": f"Account {account_id}",
                },
            )

            yield account_info, session

        logger.debug(
            f"Session provision complete: {len(self._valid_arns)} sessions yielded"
        )
