import asyncio
from collections import defaultdict

from aiobotocore.session import AioSession
from loguru import logger

from aws.auth.session_factory import (
    AccountInfo,
    clear_aws_account_sessions,
    get_all_account_sessions,
    get_inaccessible_accounts,
    initialize_aws_account_sessions,
)
from aws.auth.utils import AWSSessionError
from aws.core.helpers.utils import get_allowed_regions
from aws.probe.identity import get_policy_source_arn
from aws.probe.permissions import AwsKindPermissionVerdict
from aws.probe.simulator import SimulateOutcome, simulate_principal_policy
from integration import AWSResourceSelector
from port_ocean.core.probe import ProbeCheck, ProbeCheckStatus, ProbeContext

_MAX_CONCURRENT_ACCOUNTS = 5
_MAX_CONCURRENT_REGIONS = 10
_UNREACHABLE_REGION = "*"


class AwsPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context
        self.permission_verdict = AwsKindPermissionVerdict()
        self._account_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_ACCOUNTS)
        self._region_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REGIONS)

    async def run(self) -> None:
        try:
            await initialize_aws_account_sessions()
        except Exception as error:
            logger.warning("AWS session initialization failed during probe: {}", error)
            await self.context.fail("Failed to verify AWS authentication.")
            return

        try:
            await self._run_scoped_checks()
        finally:
            await clear_aws_account_sessions()

    async def _run_scoped_checks(self) -> None:
        accounts: list[tuple[AccountInfo, AioSession]] = []
        try:
            async for account, session in get_all_account_sessions():
                accounts.append((account, session))
        except (AWSSessionError, Exception) as error:
            logger.warning("Failed to list AWS accounts during probe: {}", error)
            await self.context.fail("Failed to verify AWS authentication.")
            return

        if not accounts:
            await self.context.fail("No AWS accounts were accessible.")
            return

        await self._fail_inaccessible_accounts()

        action_names = sorted(
            {
                action
                for kind in self.context.available_kinds
                for action in self.permission_verdict.kind_permissions.get(kind, ())
            }
        )

        account_scopes = await self._collect_account_scopes(accounts, action_names)
        if account_scopes is None:
            return

        scopes, sessions_by_account, policy_arns, collapsed_outcomes = account_scopes

        checks = await self.context.add_scopes(*scopes)
        checks_by_scope: dict[tuple[str, str], list[ProbeCheck]] = defaultdict(list)
        for check in checks:
            account_id = str(check.scopes["account"])
            region = str(check.scopes["region"])
            checks_by_scope[(account_id, region)].append(check)

        async def probe_account(account_id: str, session: AioSession) -> None:
            async with self._account_semaphore:
                collapsed = collapsed_outcomes.get(account_id)
                if collapsed is not None:
                    await self._probe_scope(
                        session,
                        _UNREACHABLE_REGION,
                        policy_arns[account_id],
                        action_names,
                        checks_by_scope[(account_id, _UNREACHABLE_REGION)],
                        collapsed,
                    )
                    return

                region_tasks = [
                    self._probe_scope(
                        session,
                        region,
                        policy_arns[account_id],
                        action_names,
                        scope_checks,
                    )
                    for (scope_account, region), scope_checks in checks_by_scope.items()
                    if scope_account == account_id
                ]
                await asyncio.gather(*region_tasks)

        await asyncio.gather(
            *(
                probe_account(account_id, session)
                for account_id, session in sessions_by_account.items()
            )
        )

    async def _collect_account_scopes(
        self,
        accounts: list[tuple[AccountInfo, AioSession]],
        action_names: list[str],
    ) -> (
        tuple[
            list[dict[str, str | int]],
            dict[str, AioSession],
            dict[str, str],
            dict[str, SimulateOutcome],
        ]
        | None
    ):
        scopes: list[dict[str, str | int]] = []
        sessions_by_account: dict[str, AioSession] = {}
        policy_arns: dict[str, str] = {}
        collapsed_outcomes: dict[str, SimulateOutcome] = {}

        for account, session in accounts:
            account_id = account["Id"]
            try:
                policy_arns[account_id] = await get_policy_source_arn(session)
            except Exception as error:
                logger.warning(
                    "sts:GetCallerIdentity failed for account {}: {}",
                    account_id,
                    error,
                )
                await self.context.fail(
                    f"Failed to verify AWS authentication for account {account_id}."
                )
                return None

            sessions_by_account[account_id] = session
            if action_names:
                outcome = await simulate_principal_policy(
                    session,
                    policy_arns[account_id],
                    action_names,
                    _UNREACHABLE_REGION,
                )
                if outcome.missing_simulate_permission:
                    collapsed_outcomes[account_id] = outcome
                    scopes.append(
                        {"account": account_id, "region": _UNREACHABLE_REGION}
                    )
                    continue

            regions = await get_allowed_regions(
                session, AWSResourceSelector(query="true")
            )
            if not regions:
                await self.context.fail(
                    f"No AWS regions were available for account {account_id}."
                )
                return None
            for region in regions:
                scopes.append({"account": account_id, "region": region})

        return scopes, sessions_by_account, policy_arns, collapsed_outcomes

    async def _fail_inaccessible_accounts(self) -> None:
        inaccessible = get_inaccessible_accounts()
        if not inaccessible:
            return

        checks = await self.context.add_scopes(
            *(
                {"account": account_id, "region": _UNREACHABLE_REGION}
                for account_id in inaccessible
            )
        )
        for check in checks:
            check.status = ProbeCheckStatus.FAILURE
            check.message = inaccessible[str(check.scopes["account"])]
        await self.context.update_progress()

    async def _probe_scope(
        self,
        session: AioSession,
        region: str,
        policy_source_arn: str,
        action_names: list[str],
        checks: list[ProbeCheck],
        outcome: SimulateOutcome | None = None,
    ) -> None:
        async with self._region_semaphore:
            if outcome is None:
                outcome = await simulate_principal_policy(
                    session, policy_source_arn, action_names, region
                )
            for check in checks:
                self._resolve_check(check, outcome)
            await self.context.update_progress()

    def _resolve_check(
        self,
        check: ProbeCheck,
        outcome: SimulateOutcome,
    ) -> None:
        if check.kind not in self.permission_verdict.kind_permissions:
            check.status, check.message = (
                ProbeCheckStatus.UNKNOWN,
                self.permission_verdict.unmapped_message(check.kind),
            )
            return

        if outcome.missing_simulate_permission or outcome.throttled:
            check.status = ProbeCheckStatus.UNKNOWN
            check.message = outcome.error_message
            return

        if outcome.error_message and not outcome.decisions:
            check.status = ProbeCheckStatus.UNKNOWN
            check.message = outcome.error_message
            return

        check.status, check.message = self.permission_verdict.verdict(
            check.kind, outcome.decisions
        )
