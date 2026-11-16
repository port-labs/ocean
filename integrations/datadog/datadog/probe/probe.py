import asyncio

from httpx import HTTPStatusError, RequestError
from loguru import logger
from port_ocean.core.probe import ProbeCheck, ProbeCheckStatus, ProbeContext

from client_manager import get_client_manager
from datadog.client import DatadogClient
from datadog.exceptions import IntegrationMissingConfigError
from datadog.probe.permissions import (
    ACCESS_DENIED_STATUS_CODES,
    IMPLICIT_PERMISSIONS,
    DatadogKindPermissionVerdict,
    authentication_failure_message,
    permissions_lookup_failure_message,
)


class AuthenticationFailedError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _org_scope_label(client: DatadogClient, index: int) -> str:
    return client.org_name or client.org_id or f"#{index + 1} ({client.api_url})"


class DatadogPermissionProbe:
    """Verifies the Datadog credentials and the permissions each kind needs.

    Per org it makes three calls, none retried: the current user (authentication),
    that user's role permissions, and the application key's scopes. Each kind's
    ``probe_permissions`` are then checked against the effective permissions. A
    failed authentication call is followed by /api/v1/validate to tell which key
    is wrong. Multi-org installs report one set of checks per org.
    """

    def __init__(self, context: ProbeContext) -> None:
        self.context = context
        self.permission_verdict = DatadogKindPermissionVerdict()

    async def run(self) -> None:
        try:
            manager = get_client_manager()
        except IntegrationMissingConfigError as error:
            await self.context.fail(str(error))
            return

        if not manager.is_multi_org:
            await self._probe_single_org(manager.clients[0])
            return

        for index, client in enumerate(manager.clients):
            await self._probe_org(client, _org_scope_label(client, index))

    async def _probe_single_org(self, client: DatadogClient) -> None:
        try:
            user_id = await self._authenticate(client)
        except AuthenticationFailedError as error:
            await self.context.fail(error.message)
            return

        checks = await self.context.setup_unscoped_checks()
        await self._resolve_checks(client, user_id, checks)

    async def _probe_org(self, client: DatadogClient, org: str) -> None:
        checks = await self.context.add_scopes({"org": org})
        try:
            user_id = await self._authenticate(client)
        except AuthenticationFailedError as error:
            await self._fail_checks(checks, error.message)
            return

        await self._resolve_checks(client, user_id, checks)

    async def _authenticate(self, client: DatadogClient) -> str:
        """Return the id of the user the credentials belong to."""
        try:
            user = await client.get_current_user()
        except HTTPStatusError as error:
            raise AuthenticationFailedError(
                await self._authentication_failure(client, error.response.status_code)
            ) from error
        except RequestError as error:
            raise AuthenticationFailedError(
                f"Datadog could not be reached while verifying authentication: {error}"
            ) from error
        return user["id"]

    @staticmethod
    async def _authentication_failure(client: DatadogClient, status_code: int) -> str:
        if status_code not in ACCESS_DENIED_STATUS_CODES:
            return authentication_failure_message(status_code=status_code)
        if client.access_token:
            return authentication_failure_message(
                status_code=status_code, invalid_key="Datadog access token"
            )

        # current_user needs both keys; /api/v1/validate checks the API key alone.
        try:
            await client.validate_api_key()
        except HTTPStatusError:
            invalid_key = "API key"
        except RequestError:
            invalid_key = None
        else:
            invalid_key = "application key"
        return authentication_failure_message(
            status_code=status_code, invalid_key=invalid_key
        )

    async def _resolve_checks(
        self, client: DatadogClient, user_id: str, checks: list[ProbeCheck]
    ) -> None:
        try:
            permissions = await self._effective_permissions(client, user_id)
        except HTTPStatusError as error:
            await self._fail_checks(
                checks, permissions_lookup_failure_message(error.response.status_code)
            )
            return
        except RequestError as error:
            await self._fail_checks(
                checks,
                f"Datadog could not be reached while reading permissions: {error}",
            )
            return

        for check in checks:
            check.status, check.message = self.permission_verdict.verdict(
                check.kind, permissions
            )
        await self.context.update_progress()

    async def _effective_permissions(
        self, client: DatadogClient, user_id: str
    ) -> dict[str, bool]:
        role_permissions, scopes = await asyncio.gather(
            client.get_user_permissions(user_id),
            self._application_key_scopes(client),
        )
        granted = role_permissions | IMPLICIT_PERMISSIONS
        if scopes is not None:
            granted &= set(scopes)
        return {permission: True for permission in granted}

    @staticmethod
    async def _application_key_scopes(client: DatadogClient) -> list[str] | None:
        """Return the scopes of the configured application key, or None when it
        is unscoped (it then has all of its owner's permissions) or its scopes
        can't be determined."""
        if client.access_token:
            return None

        try:
            keys = await client.get_current_user_application_keys()
        except HTTPStatusError as error:
            logger.warning(
                "Could not read the application key's scopes "
                f"(HTTP {error.response.status_code}); checking the owner's role "
                "permissions only"
            )
            return None

        last4 = client.dd_app_key[-4:]
        matches = [key for key in keys if key["attributes"].get("last4") == last4]
        if len(matches) != 1:
            logger.warning(
                f"Found {len(matches)} application keys of the current user ending "
                "with the configured key; checking the owner's role permissions only"
            )
            return None
        return matches[0]["attributes"].get("scopes")

    async def _fail_checks(self, checks: list[ProbeCheck], message: str) -> None:
        for check in checks:
            check.status = ProbeCheckStatus.FAILURE
            check.message = message
        await self.context.update_progress()
