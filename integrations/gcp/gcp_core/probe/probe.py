import asyncio
from asyncio import BoundedSemaphore
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from google.api_core.exceptions import GoogleAPICallError, PermissionDenied
from google.auth.exceptions import GoogleAuthError
from loguru import logger

import gcp_core.clients as clients
from gcp_core.helpers.ratelimiter.base import MAXIMUM_CONCURRENT_REQUESTS
from gcp_core.probe.permissions import GcpKindPermissionVerdict
from gcp_core.search.paginated_query import DEFAULT_REQUEST_TIMEOUT, PAGE_SIZE
from gcp_core.utils import AssetTypesWithSpecialHandling
from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
from port_ocean.core.probe import ProbeCheck, ProbeCheckStatus, ProbeContext

_MAX_LISTED_GROUPS = 5
_MAX_NAMED_CONTAINERS = 5


@dataclass(frozen=True)
class _ContainerResult:
    """Exactly one of granted/error is set: the permissions, or why they are unknown."""

    container: str
    granted: frozenset[str] | None
    error: str | None


@dataclass(frozen=True)
class _ContainerLevel:
    label: str
    kinds: tuple[str, ...]
    get_client: Callable[[], Any]
    search_method: str
    implied_permission: str
    """The permission this level's search filters on, so discovery proves it."""


_LEVELS = (
    _ContainerLevel(
        label="project",
        kinds=(
            AssetTypesWithSpecialHandling.PROJECT.value,
            AssetTypesWithSpecialHandling.TOPIC.value,
            AssetTypesWithSpecialHandling.SUBSCRIPTION.value,
            AssetTypesWithSpecialHandling.CLOUD_RESOURCE.value,
            AssetTypesWithSpecialHandling.IAM_POLICY.value,
            CUSTOM_KIND,
        ),
        get_client=clients.get_projects_client,
        search_method="search_projects",
        implied_permission="resourcemanager.projects.get",
    ),
    _ContainerLevel(
        label="folder",
        kinds=(AssetTypesWithSpecialHandling.FOLDER.value,),
        get_client=clients.get_folders_client,
        search_method="search_folders",
        implied_permission="resourcemanager.folders.get",
    ),
    _ContainerLevel(
        label="organization",
        kinds=(AssetTypesWithSpecialHandling.ORGANIZATION.value,),
        get_client=clients.get_organizations_client,
        search_method="search_organizations",
        implied_permission="resourcemanager.organizations.get",
    ),
)


def _summarize(label: str, total: int, findings: list[tuple[str, str]]) -> str:
    """Group containers by the verdict they produced, largest group first.

    A group short enough to name is named, so the reader can go and fix exactly those
    containers; a longer one gets its count alone, since the remedy there is a grant
    higher up and a partial list would not say which containers it left out.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for message, container in findings:
        groups[message].append(container)
    ranked = sorted(groups.items(), key=lambda group: len(group[1]), reverse=True)
    noun = label if total == 1 else f"{label}s"
    summary = "; ".join(
        f"{len(containers)} of {total} {noun} - {message}"
        + (
            f" ({', '.join(containers)})"
            if len(containers) <= _MAX_NAMED_CONTAINERS
            else ""
        )
        for message, containers in ranked[:_MAX_LISTED_GROUPS]
    )
    remaining = len(ranked) - _MAX_LISTED_GROUPS
    if remaining > 0:
        summary += f" (and {remaining} more)"
    return summary


class GcpPermissionProbe:
    """Reports, per kind, whether the credentials hold the IAM permissions to sync it.

    A kind resolves one of two ways. The resourcemanager search methods only return
    containers the caller holds `<level>.get` on, and a full resync reads the Project,
    Folder and Organization kinds straight off that same search, so discovery finding
    anything at all settles that permission - one container is fetched and nothing is
    tested. It is subtracted from the test request too, so the two paths rest on the
    same assumption rather than re-asking a question discovery already answered.

    Every other kind is tested container by container, because resync hides a
    per-container gap: `search_all_resources_in_project` and the Pub/Sub listings
    swallow PermissionDenied and carry on (`resource_searches.py`), so a gap on one
    project out of many surfaces as a successful resync with that project's entities
    reconciled away. Testing a single project would call that green.

    Checks are unscoped - one per kind, not one per kind x container. Per-project
    scopes were tried and rejected: `add_scopes` registers every available kind at
    every scope, so each project would carry a Folder row that cannot be answered,
    since GCP rejects a cross-level permission outright. The whole check list is also
    re-serialized on every update_progress, so it must not grow with the size of the
    org - a 500-project org would otherwise post 3,000 checks for the six
    project-level kinds. The per-container detail goes into the check message instead,
    grouped by verdict, naming the containers behind a group while they are few enough
    to list and falling back to a count. That message is the only place the user
    learns which containers are affected.

    IAM grants are verified, not whether the backing API is enabled on the container -
    a granted cloudasset permission still fails with SERVICE_DISABLED at resync. That
    caveat reaches the UI through probe_description on the cloudasset-backed kinds.
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
            results = await asyncio.gather(
                *(self._run_level(level, checks) for level in _LEVELS),
                return_exceptions=True,
            )
        finally:
            await clients.close()

        # every mapped kind has been resolved by its level, including on the way out
        # of a failure, so whatever is still pending belongs to no level at all
        for kind, check in checks.items():
            if check.status is ProbeCheckStatus.PENDING:
                check.status = ProbeCheckStatus.UNKNOWN
                check.message = self.permission_verdict.unmapped_message(kind)

        errors = [result for result in results if isinstance(result, BaseException)]
        auth_errors = [error for error in errors if isinstance(error, GoogleAuthError)]
        if auth_errors:
            await self.context.fail(
                f"Failed to verify GCP authentication: {auth_errors[0]}"
            )
            return
        if errors:
            await self.context.fail(
                "Failed to verify GCP permissions: "
                + "; ".join(f"{type(error).__name__}: {error}" for error in errors)
            )
            return
        await self.context.update_progress()

    async def _run_level(
        self,
        level: _ContainerLevel,
        checks: dict[str, ProbeCheck],
    ) -> None:
        level_checks = [checks[kind] for kind in level.kinds if kind in checks]
        if not level_checks:
            logger.debug(
                f"No {level.label}-level kinds are being probed, skipping {level.label} discovery"
            )
            return

        try:
            await self._probe_level(level, level_checks)
        except Exception as error:
            # run() turns this into an overall failure; the checks still have to say
            # something, or they reach Port as PENDING after the probe has ended
            await self._resolve_all(
                level_checks,
                ProbeCheckStatus.UNKNOWN,
                f"Could not verify {level.label}-level permissions: {error}",
            )
            raise

    async def _probe_level(
        self,
        level: _ContainerLevel,
        level_checks: list[ProbeCheck],
    ) -> None:
        answered_by_discovery: list[ProbeCheck] = []
        needs_testing: list[ProbeCheck] = []
        unanswered: set[str] = set()
        for check in level_checks:
            remaining = set(self.permission_verdict.kind_permissions[check.kind]) - {
                level.implied_permission
            }
            (needs_testing if remaining else answered_by_discovery).append(check)
            unanswered.update(remaining)

        try:
            if needs_testing:
                containers = await self._discover(level)
            else:
                containers = await self._discover(level, limit=1)
        except PermissionDenied as error:
            await self._resolve_all(
                level_checks,
                ProbeCheckStatus.FAILURE,
                f"Not allowed to list GCP {level.label}s: {error}",
            )
            return
        except GoogleAPICallError as error:
            # the search filters by permission rather than refusing, so anything else
            # reaching here is a call that did not complete, not a grant that is absent
            await self._resolve_all(
                level_checks,
                ProbeCheckStatus.UNKNOWN,
                f"Could not list GCP {level.label}s: {error}",
            )
            return

        if not containers:
            await self._resolve_all(
                level_checks,
                ProbeCheckStatus.UNKNOWN,
                f"No GCP {level.label} was discovered. Search returns only "
                f"{level.label}s where {level.implied_permission} is granted, so "
                f"either none exist or the credentials are missing it.",
            )
            return

        for check in answered_by_discovery:
            check.status, check.message = self._granted(check.kind)

        if needs_testing:
            permissions = sorted(unanswered)
            try:
                async with asyncio.TaskGroup() as group:
                    tasks = [
                        group.create_task(
                            self._test_container(level, container, permissions)
                        )
                        for container in containers
                    ]
            except ExceptionGroup as raised:  # noqa: F821
                # the TaskGroup has already cancelled the siblings, so nothing is
                # still calling GCP once run() reaches clients.close(). Unwrap, or
                # run() cannot tell an auth failure from any other kind - and an auth
                # error anywhere in the group has to win, or an unrelated failure
                # ordered before it masks the one run() classifies on.
                auth_errors = raised.subgroup(GoogleAuthError)
                raise (auth_errors or raised).exceptions[0]
            outcomes = [task.result() for task in tasks]
            for check in needs_testing:
                check.status, check.message = self._combine(level, check.kind, outcomes)
        await self.context.update_progress()

    async def _discover(
        self, level: _ContainerLevel, *, limit: int | None = None
    ) -> list[str]:
        """Every container at this level, or just the first `limit` of them.

        The page size and the early stop both come from `limit`: the pager fetches
        each further page on demand, so either on its own would walk the whole org.
        """
        pager = await getattr(level.get_client(), level.search_method)(
            request={"page_size": min(limit, PAGE_SIZE) if limit else PAGE_SIZE},
            retry=None,
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )
        containers: list[str] = []
        async for container in pager:
            containers.append(container.name)
            if limit and len(containers) >= limit:
                break
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
                    retry=None,
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
            except GoogleAPICallError as error:
                # including PermissionDenied: this call needs no permission of its
                # own, so a denial means the container is unreachable, not that the
                # grant is absent. An absent grant comes back in the response.
                logger.warning(
                    f"Failed to test IAM permissions on {container}: {error}"
                )
                return _ContainerResult(
                    container, None, f"Could not verify access: {error}"
                )
        return _ContainerResult(container, frozenset(response.permissions), None)

    def _combine(
        self,
        level: _ContainerLevel,
        kind: str,
        results: list[_ContainerResult],
    ) -> tuple[ProbeCheckStatus, str]:
        failures: list[tuple[str, str]] = []
        unknowns: list[tuple[str, str]] = []
        for result in results:
            if result.granted is None:
                unknowns.append((str(result.error), result.container))
                continue
            status, message = self.permission_verdict.verdict(
                kind, dict.fromkeys(result.granted, True)
            )
            if status is ProbeCheckStatus.FAILURE:
                failures.append((message, result.container))
            elif status is ProbeCheckStatus.UNKNOWN:
                unknowns.append((message, result.container))

        total = len(results)
        if failures:
            # a denial is the actionable verdict, so it leads; the containers that
            # could not be checked are still counted, to save a second probe run
            summary = _summarize(level.label, total, failures)
            if unknowns:
                summary += f", and {len(unknowns)} of {total} could not be checked"
            return ProbeCheckStatus.FAILURE, summary
        if unknowns:
            return ProbeCheckStatus.UNKNOWN, _summarize(level.label, total, unknowns)
        return self._granted(kind)

    def _granted(self, kind: str) -> tuple[ProbeCheckStatus, str]:
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
