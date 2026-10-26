import httpx
from loguru import logger

from plain.client import PlainClient
from plain.exceptions import PlainGraphQLError, PlainHTTPError
from plain.probe.permissions import (
    PlainKindPermissionVerdict,
    authentication_failure_message,
)
from port_ocean.core.probe import ProbeCheck, ProbeCheckStatus, ProbeContext


def _is_unauthenticated_graphql_error(error: PlainGraphQLError) -> bool:
    for item in error.errors:
        if not isinstance(item, dict):
            continue
        extensions = item.get("extensions")
        if isinstance(extensions, dict) and extensions.get("code") == "UNAUTHENTICATED":
            return True
        message = str(item.get("message") or "").lower()
        if "unauthenticated" in message or "unauthorized" in message:
            return True
    return False


class PlainPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context
        self.permission_verdict = PlainKindPermissionVerdict()
        self.client = PlainClient()

    async def run(self) -> None:
        try:
            await self.client.verify_authentication()
        except PlainHTTPError as error:
            await self.context.fail(
                authentication_failure_message(status_code=error.status_code)
            )
            return
        except PlainGraphQLError as error:
            if _is_unauthenticated_graphql_error(error):
                await self.context.fail(authentication_failure_message())
            else:
                await self.context.fail(
                    "Failed to verify Plain authentication: " f"{error}"
                )
            return
        except httpx.RequestError as error:
            await self.context.fail(
                "Plain could not be reached while verifying authentication: " f"{error}"
            )
            return

        checks = await self.context.setup_unscoped_checks()

        try:
            permissions = await self.client.get_my_permissions()
        except PlainHTTPError as error:
            await self._fail_permission_checks(
                checks,
                (
                    f"Plain returned HTTP {error.status_code} "
                    "while fetching API key permissions."
                ),
            )
            return
        except PlainGraphQLError as error:
            await self._fail_permission_checks(
                checks,
                f"Plain returned a GraphQL error while fetching API key permissions: {error}",
            )
            return
        except httpx.RequestError as error:
            await self._fail_permission_checks(
                checks,
                (
                    "Plain could not be reached while fetching API key permissions: "
                    f"{error}"
                ),
            )
            return

        await self._resolve_permission_checks(checks, permissions)

    async def _fail_permission_checks(
        self,
        checks: list[ProbeCheck],
        message: str,
    ) -> None:
        logger.warning("Plain permission probe failed: {}", message)
        for check in checks:
            check.status = ProbeCheckStatus.FAILURE
            check.message = message
        await self.context.update_progress()

    async def _resolve_permission_checks(
        self,
        checks: list[ProbeCheck],
        permissions: dict[str, bool],
    ) -> None:
        for check in checks:
            check.status, check.message = self.permission_verdict.verdict(
                check.kind,
                permissions,
            )
        await self.context.update_progress()
