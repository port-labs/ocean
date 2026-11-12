import asyncio
from asyncio import BoundedSemaphore
from dataclasses import dataclass
from typing import Any, Callable, cast

from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from loguru import logger

import gcp_core.clients as clients
from gcp_core.helpers.ratelimiter.base import MAXIMUM_CONCURRENT_REQUESTS
from gcp_core.helpers.retry.async_retry import async_retry
from gcp_core.probe.permissions import GcpKindPermissionVerdict
from gcp_core.search.paginated_query import DEFAULT_REQUEST_TIMEOUT, paginated_query
from gcp_core.utils import AssetTypesWithSpecialHandling
from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
from port_ocean.core.probe import ProbeCheck, ProbeCheckStatus, ProbeContext

_MAX_LISTED_CONTAINERS = 5

# (container, granted permissions, error) - exactly one of the last two is set.
_ContainerResult = tuple[str, frozenset[str] | None, str | None]


@dataclass(frozen=True)
class _ContainerLevel:
    label: str
    kinds: tuple[str, ...]
    get_client: Callable[[], Any]
    search_method: str
    response_field: str


# testIamPermissions rejects the whole request with INVALID_ARGUMENT when a
# permission does not apply to the resource, so each level may only be asked
# about the permissions of the kinds that live at that level.
_LEVELS = (
    _ContainerLevel(
        label="project",
        kinds=(
            AssetTypesWithSpecialHandling.PROJECT.value,
            AssetTypesWithSpecialHandling.TOPIC.value,
            AssetTypesWithSpecialHandling.SUBSCRIPTION.value,
            AssetTypesWithSpecialHandling.CLOUD_RESOURCE.value,
            CUSTOM_KIND,
        ),
        get_client=clients.get_projects_client,
        search_method="search_projects",
        response_field="projects",
    ),
    _ContainerLevel(
        label="folder",
        kinds=(AssetTypesWithSpecialHandling.FOLDER.value,),
        get_client=clients.get_folders_client,
        search_method="search_folders",
        response_field="folders",
    ),
    _ContainerLevel(
        label="organization",
        kinds=(AssetTypesWithSpecialHandling.ORGANIZATION.value,),
        get_client=clients.get_organizations_client,
        search_method="search_organizations",
        response_field="organizations",
    ),
)


def _summarize(messages: list[str]) -> str:
    shown = messages[:_MAX_LISTED_CONTAINERS]
    summary = "; ".join(shown)
    remaining = len(messages) - len(shown)
    if remaining:
        summary += f" (and {remaining} more)"
    return summary


class GcpPermissionProbe:
    """Reports, per kind, whether the credentials hold the IAM permissions to sync it.

    IAM grants are verified, not whether the backing API is enabled on the container -
    a granted cloudasset permission still fails with SERVICE_DISABLED at resync.
    """

    def __init__(self, context: ProbeContext) -> None:
        self.context = context
        self.permission_verdict = GcpKindPermissionVerdict()
        self._semaphore = BoundedSemaphore(MAXIMUM_CONCURRENT_REQUESTS)

    async def run(self) -> None:
        checks = {
            check.kind: check for check in await self.context.setup_unscoped_checks()
        }

        try:
            # gather does not cancel siblings, so a raising level must not leave the
            # others reporting into an already failed probe.
            results = await asyncio.gather(
                *(self._run_level(level, checks) for level in _LEVELS),
                return_exceptions=True,
            )
        finally:
            await clients.close()

        errors = [result for result in results if isinstance(result, BaseException)]
        for error in errors:
            if isinstance(error, GoogleAuthError):
                await self.context.fail(f"Failed to verify GCP authentication: {error}")
                return
        if errors:
            raise errors[0]

        for kind, check in checks.items():
            if check.status is ProbeCheckStatus.PENDING:
                check.status = ProbeCheckStatus.UNKNOWN
                check.message = self.permission_verdict.unmapped_message(kind)
        await self.context.update_progress()

    async def _run_level(
        self,
        level: _ContainerLevel,
        checks: dict[str, ProbeCheck],
    ) -> None:
        level_checks = [
            checks[kind]
            for kind in level.kinds
            if kind in checks and self.permission_verdict.kind_permissions.get(kind)
        ]
        if not level_checks:
            return

        permissions = sorted(
            {
                permission
                for check in level_checks
                for permission in self.permission_verdict.kind_permissions[check.kind]
            }
        )

        try:
            containers = await self._discover(level)
        except GoogleAPICallError as error:
            await self._resolve_all(
                level_checks,
                ProbeCheckStatus.FAILURE,
                f"Failed to list GCP {level.label}s: {error.message}",
            )
            return

        if not containers:
            await self._resolve_all(
                level_checks,
                ProbeCheckStatus.UNKNOWN,
                f"No GCP {level.label} was discovered, so {level.label}-level "
                "permissions could not be verified.",
            )
            return

        results = await asyncio.gather(
            *(
                self._test_container(level, container, permissions)
                for container in containers
            )
        )
        for check in level_checks:
            check.status, check.message = self._combine(check.kind, results)
        await self.context.update_progress()

    async def _discover(self, level: _ContainerLevel) -> list[str]:
        containers: list[str] = []
        async for page in paginated_query(
            level.get_client(),
            level.search_method,
            {},
            lambda response: [
                container.name for container in getattr(response, level.response_field)
            ],
        ):
            containers.extend(cast(list[str], page))
        return containers

    async def _test_container(
        self,
        level: _ContainerLevel,
        container: str,
        permissions: list[str],
    ) -> _ContainerResult:
        async with self._semaphore:
            try:
                response = await level.get_client().test_iam_permissions(
                    request={"resource": container, "permissions": permissions},
                    retry=async_retry,
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
            except GoogleAPICallError as error:
                logger.warning(
                    f"Failed to test IAM permissions on {container}: {error}"
                )
                return container, None, f"Could not verify access: {error.message}"
        return container, frozenset(response.permissions), None

    def _combine(
        self,
        kind: str,
        results: list[_ContainerResult],
    ) -> tuple[ProbeCheckStatus, str]:
        failures: list[str] = []
        unknowns: list[str] = []
        for container, granted, error in results:
            if granted is None:
                unknowns.append(f"{container}: {error}")
                continue
            status, message = self.permission_verdict.verdict(
                kind, dict.fromkeys(granted, True)
            )
            if status is ProbeCheckStatus.FAILURE:
                failures.append(f"{container}: {message}")
            elif status is ProbeCheckStatus.UNKNOWN:
                unknowns.append(f"{container}: {message}")

        if failures:
            return ProbeCheckStatus.FAILURE, _summarize(failures)
        if unknowns:
            return ProbeCheckStatus.UNKNOWN, _summarize(unknowns)
        return ProbeCheckStatus.SUCCESS, self.permission_verdict.granted_message(
            self.permission_verdict.kind_permissions[kind]
        )

    async def _resolve_all(
        self,
        checks: list[ProbeCheck],
        status: ProbeCheckStatus,
        message: str,
    ) -> None:
        for check in checks:
            check.status = status
            check.message = message
        await self.context.update_progress()
