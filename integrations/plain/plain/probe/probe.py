import httpx

from plain.client import PlainClient
from plain.exceptions import PlainGraphQLError, PlainHTTPError
from plain.probe.permissions import (
    PlainKindPermissionVerdict,
    authentication_failure_message,
)
from port_ocean.core.probe import ProbeCheck, ProbeContext
from port_ocean.exceptions.clients import BlockedIPError


def _is_unauthenticated_graphql_error(error: PlainGraphQLError) -> bool:
    for item in error.errors:
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
            permissions = await self.client.get_my_permissions(skip_retry=True)
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
        except BlockedIPError as error:
            await self.context.fail(
                "Plain API host was blocked by network security policy: " f"{error}"
            )
            return
        except httpx.ConnectError as error:
            # Provide clear message for SSL/certificate errors vs generic connection failures
            error_str = str(error).lower()
            if "ssl" in error_str or "certificate" in error_str or "tls" in error_str:
                await self.context.fail(
                    "Could not establish a secure connection to Plain API. "
                    "This may indicate an SSL/TLS certificate verification failure. "
                    f"Details: {error}"
                )
            else:
                await self.context.fail(
                    "Plain could not be reached while verifying authentication: "
                    f"{error}"
                )
            return
        except httpx.RequestError as error:
            await self.context.fail(
                "Plain could not be reached while verifying authentication: " f"{error}"
            )
            return

        checks = await self.context.setup_unscoped_checks()
        await self._resolve_permission_checks(checks, permissions)

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
