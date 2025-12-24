from aws.auth.strategies.base import (
    AWSSessionStrategy,
    HealthCheckMixin,
    CachedHealthCheckMixin,
)
from aws.auth.utils import (
    AWSOrganizationsNotInUseError,
    AWSSessionError,
    extract_account_from_arn,
)
from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from loguru import logger
from port_ocean.utils.cache import cache_coroutine_result
import asyncio
from typing import Any, AsyncIterator, Dict, List
from botocore.utils import ArnParser


class OrganizationDiscoveryMixin(AWSSessionStrategy):
    """Mixin for organizations discovery."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

        self._organization_role_details: dict[str, str] | None = None
        self._valid_arns: list[str] = []
        self._valid_sessions: dict[str, AioSession] = {}
        self._organization_session: AioSession | None = None
        self._discovered_accounts: List[Dict[str, str]] = []

    @property
    def valid_arns(self) -> list[str]:
        """Get the list of valid ARNs that passed health check."""
        return getattr(self, "_valid_arns", [])

    @property
    def valid_sessions(self) -> dict[str, AioSession]:
        """Get the dictionary of valid sessions that passed health check."""
        return getattr(self, "_valid_sessions", {})

    def _get_organization_account_role_arn(self) -> str:
        """Get the organization account role ARN from the configuration."""
        account_role_arn = self.config.get("account_role_arn")

        if not account_role_arn:
            raise AWSSessionError(
                "account_role_arn is required and must be a non-empty string"
            )

        return account_role_arn

    def _get_organization_account_role_details(self) -> dict[str, str]:
        """Get the account role ARN from the configuration."""
        if self._organization_role_details:
            return self._organization_role_details

        organization_role_arn = self._get_organization_account_role_arn()

        # validate role arn format
        if not organization_role_arn.startswith("arn:aws:iam::"):
            raise AWSSessionError("account_role_arn must be a valid ARN")

        arn_data = ArnParser().parse_arn(arn=organization_role_arn)

        self._organization_role_details = arn_data
        return self._organization_role_details

    def _build_role_arn(self, account_id: str) -> str:
        """Build the role ARN for the organization account."""
        details = self._get_organization_account_role_details()
        return f"arn:aws:iam::{account_id}:{details['resource']}"

    async def _get_organization_session(self) -> AioSession:
        """Get or create the organization session for the management account."""
        if self._organization_session:
            return self._organization_session

        details = self._get_organization_account_role_details()
        logger.info(f"Assuming organization role: {details['resource']}")

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

    async def discover_accounts(self) -> List[Dict[str, str]]:
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
                raise AWSOrganizationsNotInUseError(
                    "Cannot access AWS Organizations API - check permissions"
                )
            elif "AWSOrganizationsNotInUse" in str(e):
                logger.warning("AWS Organizations is not enabled in this account")
                raise AWSOrganizationsNotInUseError(
                    "AWS Organizations is not enabled in this account"
                )
            else:
                logger.error(f"Error discovering accounts: {e}")
                raise AWSSessionError(f"Failed to discover accounts: {e}")

    def _add_account_to_valid_accounts(
        self, account_id: str, session: AioSession
    ) -> None:
        """Add an account to the list of valid accounts."""
        role_arn = self._build_role_arn(account_id)
        self._valid_arns.append(role_arn)
        self._valid_sessions[role_arn] = session

    async def _fallback_to_single_account(self) -> bool:
        """Fall back to single account mode when organizations is not available."""
        try:
            logger.info("Attempting single account mode")
            organization_session = await self._get_organization_session()
            details = self._get_organization_account_role_details()
            arn = self._get_organization_account_role_arn()
            account_id = details["account"]

            # Add this account to valid accounts
            self._add_account_to_valid_accounts(account_id, organization_session)

            # Set discovered accounts to just this one
            self._discovered_accounts = [
                {
                    "Id": account_id,
                    "Name": f"Account {account_id}",
                    "Email": "",
                    "Arn": arn,
                }
            ]

            return True

        except Exception as e:
            logger.error(f"Fallback to single account mode failed: {e}")
            raise AWSSessionError(
                f"Both organizations and single account modes failed: {e}"
            )


class OrganizationsHealthCheckMixin(OrganizationDiscoveryMixin, CachedHealthCheckMixin):
    """Mixin for organizations health checking with batching and concurrency."""

    DEFAULT_CONCURRENCY = 10
    DEFAULT_BATCH_SIZE = 10

    def _get_cache_key_params(self) -> dict[str, str | None]:
        """Get parameters that should be used for cache key generation."""
        return {
            "role_arn": self._get_organization_account_role_arn(),
            "external_id": self.config.get("external_id"),
            "region": self.config.get("region"),
        }

    async def _restore_from_cache_data(self, cache_data: dict[str, Any]) -> bool:
        """Initialize strategy state from healthcheck data (from cache or newly generated)."""
        try:
            valid_arns = cache_data.get("valid_arns", [])
            discovered_accounts = cache_data.get("discovered_accounts", [])

            if not valid_arns:
                logger.warning("Healthcheck data contains no valid account ARNs")
                return False

            # Restore discovered accounts
            self._discovered_accounts = discovered_accounts or []

            # Initialize sessions for valid ARNs
            self._valid_arns = []
            self._valid_sessions = {}

            logger.info(f"Initializing AWS sessions for {len(valid_arns)} validated account ARNs")
            for role_arn in valid_arns:
                account_id = extract_account_from_arn(role_arn)
                session = await self._can_assume_role_in_account(account_id)
                if session:
                    self._valid_arns.append(role_arn)
                    self._valid_sessions[role_arn] = session
                else:
                    logger.warning(
                        f"Failed to initialize session for {role_arn}, skipping"
                    )

            if not self._valid_arns:
                logger.error("Failed to initialize any AWS sessions")
                return False

            logger.info(
                f"Successfully initialized {len(self._valid_arns)}/{len(valid_arns)} AWS sessions"
            )
            return True

        except Exception as e:
            logger.error(f"Error initializing sessions: {e}", exc_info=True)
            return False

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

    @cache_coroutine_result()
    async def _get_healthcheck_data(
        self,
        role_arn: str,
        external_id: str | None,
        region: str | None,
    ) -> dict[str, Any]:
        """
        Get healthcheck data. Decorator automatically handles caching.
        This method only runs if cache miss.
        Returns dict with cacheable data (valid_arns, discovered_accounts).
        """
        logger.info("Performing account discovery and role validation")

        # Discover accounts first
        accounts = await self.discover_accounts()
        if not accounts:
            logger.warning("No accounts discovered in the organization")
            return {"valid_arns": [], "discovered_accounts": []}

        logger.info(f"Starting health check for {len(accounts)} discovered accounts")

        # Validate role assumption for each account
        valid_arns: list[str] = []
        discovered_accounts: list[Dict[str, str]] = []
        semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async def check_account(
            account: Dict[str, str],
        ) -> tuple[str, str | None]:
            """Check if role can be assumed in account. Returns (role_arn, role_arn or None)."""
            async with semaphore:
                session = await self._can_assume_role_in_account(account["Id"])
                role_arn = self._build_role_arn(account["Id"])
                return role_arn if session else None

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
                    role_arn_result = await task
                    if role_arn_result:
                        valid_arns.append(role_arn_result)
                        discovered_accounts.append(account)
                        successful += 1
                        logger.debug(
                            f"Role '{role_arn_result}' assumption validated for account {account['Id']}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Health check failed for account {account['Id']}: {e}"
                    )

            logger.debug(
                f"Batch {batch_num}/{total_batches}: {successful}/{len(batch)} accounts validated"
            )

        logger.info(
            f"Health check complete: {len(valid_arns)}/{len(accounts)} accounts accessible"
        )

        if not valid_arns:
            raise AWSSessionError("No accounts are accessible after health check")

        # Return cacheable data (no AioSession objects - they're not pickleable)
        return {
            "valid_arns": valid_arns,
            "discovered_accounts": discovered_accounts,
        }

    async def healthcheck(self) -> bool:
        """Perform health check by discovering accounts and validating role assumption."""
        try:
            # Get cache key parameters
            params = self._get_cache_key_params()

            # Get healthcheck data (decorator handles cache automatically)
            cache_data = await self._get_healthcheck_data(**params)

            # Initialize sessions from healthcheck data
            if not await self._restore_from_cache_data(cache_data):
                raise AWSSessionError(
                    "Failed to initialize sessions or no valid accounts found"
                )

            return True

        except AWSOrganizationsNotInUseError:
            logger.info("Falling back to single account mode")
            return await self._fallback_to_single_account()
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
            logger.info("No cached healthcheck results found, running healthcheck...")
            await self.healthcheck()
        else:
            logger.debug(
                f"Using cached healthcheck results: {len(self._valid_arns)} accounts already validated"
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

            logger.debug(
                f"Yielding session for account {account_id} with role {role_arn}"
            )
            yield account_info, session

        logger.info(
            f"Session provision complete: {len(self._valid_arns)} sessions yielded"
        )
