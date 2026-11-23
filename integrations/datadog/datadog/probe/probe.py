import asyncio
from typing import Any

from httpx import HTTPStatusError, RequestError
from loguru import logger
from port_ocean.core.probe import (
    ProbeCheck,
    ProbeCheckStatus,
    ProbeContext,
    ProbeStatus,
)

from client_manager import get_client_manager
from datadog.client import DatadogClient
from datadog.exceptions import IntegrationMissingConfigError
from datadog.probe.permissions import (
    ACCESS_DENIED_STATUS_CODES,
    IMPLICIT_PERMISSIONS,
    DatadogKindPermissionVerdict,
    authentication_failure_message,
    permissions_lookup_failure_message,
    unverified_scopes_message,
)


class AuthenticationFailedError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _configured_org_label(client: DatadogClient, index: int) -> str:
    """A unique ``org`` scope value from the configuration, used when Datadog
    can't tell which org the credentials belong to. Org names can repeat, so the
    org id is shown when known, and the position in the credential map otherwise."""
    if client.org_id:
        return (
            f"{client.org_name} ({client.org_id})" if client.org_name else client.org_id
        )
    return f"{client.org_name or client.api_url} (#{index + 1})"


def _current_user_org_label(current_user: dict[str, Any]) -> str | None:
    """The org the credentials belong to, as ``name (public id)``, from the
    /api/v2/current_user response (its ``org`` relationship and included org)."""
    org_id = (
        current_user["data"].get("relationships", {}).get("org", {}).get("data", {})
    ).get("id")
    if not org_id:
        return None
    for item in current_user.get("included", []):
        if item.get("type") == "orgs" and item.get("id") == org_id:
            attributes = item.get("attributes", {})
            public_id = attributes.get("public_id") or org_id
            name = attributes.get("name")
            return f"{name} ({public_id})" if name else public_id
    return org_id


class DatadogPermissionProbe:
    """Verifies the Datadog credentials and the permissions each kind needs.

    Per org it makes three calls, none retried: the current user (authentication,
    and the org the credentials belong to), that user's role permissions, and the
    application key's scopes. Each kind's ``probe_permissions`` are then checked
    against the effective permissions. A failed authentication call is followed
    by /api/v1/validate to tell which key is wrong.

    Every check is scoped by ``org``, as the spec declares, including single-org
    installs. A rejected single-org configuration fails the whole probe; in a
    multi-org setup it fails only that org's checks.
    """

    def __init__(self, context: ProbeContext) -> None:
        self.context = context
        self.permission_verdict = DatadogKindPermissionVerdict()
        self._unverified_scope_orgs: list[str] = []

    async def run(self) -> None:
        try:
            manager = get_client_manager()
        except IntegrationMissingConfigError as error:
            await self.context.fail(str(error))
            return

        if not manager.clients:
            await self.context.fail("No Datadog organizations were accessible.")
            return

        for index, client in enumerate(manager.clients):
            await self._probe_org(client, index, multi_org=manager.is_multi_org)

        if (
            self._unverified_scope_orgs
            and self.context.status is not ProbeStatus.FAILED
        ):
            self.context.message = unverified_scopes_message(
                self._unverified_scope_orgs if manager.is_multi_org else None
            )

    async def _probe_org(
        self, client: DatadogClient, index: int, *, multi_org: bool
    ) -> None:
        try:
            current_user = await self._authenticate(client)
        except AuthenticationFailedError as error:
            if not multi_org:
                await self.context.fail(error.message)
                return
            checks = await self.context.add_scopes(
                {"org": _configured_org_label(client, index)}
            )
            await self._mark_checks(checks, ProbeCheckStatus.FAILURE, error.message)
            return

        org = _current_user_org_label(current_user) or _configured_org_label(
            client, index
        )
        checks = await self.context.add_scopes({"org": org})
        await self._resolve_checks(client, current_user["data"]["id"], org, checks)

    async def _authenticate(self, client: DatadogClient) -> dict[str, Any]:
        """Return the /api/v2/current_user response for the credentials."""
        try:
            return await client.get_current_user()
        except HTTPStatusError as error:
            raise AuthenticationFailedError(
                await self._authentication_failure(client, error.response.status_code)
            ) from error
        except RequestError as error:
            raise AuthenticationFailedError(
                f"Datadog could not be reached while verifying authentication: {error}"
            ) from error

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
        self, client: DatadogClient, user_id: str, org: str, checks: list[ProbeCheck]
    ) -> None:
        required = {
            permission
            for check in checks
            for permission in self.permission_verdict.kind_permissions.get(
                check.kind, ()
            )
        }
        try:
            permissions = await self._effective_permissions(
                client, user_id, required, org
            )
        except HTTPStatusError as error:
            await self._mark_checks(
                checks,
                ProbeCheckStatus.UNKNOWN,
                permissions_lookup_failure_message(error.response.status_code),
            )
            return
        except RequestError as error:
            await self._mark_checks(
                checks,
                ProbeCheckStatus.UNKNOWN,
                f"Datadog could not be reached while fetching user permissions: {error}",
            )
            return

        for check in checks:
            check.status, check.message = self.permission_verdict.verdict(
                check.kind, permissions
            )
        await self.context.update_progress()

    async def _effective_permissions(
        self, client: DatadogClient, user_id: str, required: set[str], org: str
    ) -> dict[str, bool]:
        """Return the *required* permissions the credentials hold. Datadog can't
        be asked about specific permissions, so the owner's full list is fetched
        and narrowed to the ones the selected kinds need."""
        role_permissions, scopes = await asyncio.gather(
            client.get_user_permissions(user_id),
            self._application_key_scopes(client, org),
        )
        granted = (role_permissions | IMPLICIT_PERMISSIONS) & required
        if scopes is not None:
            granted &= set(scopes)
        return {permission: True for permission in granted}

    async def _application_key_scopes(
        self, client: DatadogClient, org: str
    ) -> list[str] | None:
        """Return the scopes of the configured application key, or None when it
        is unscoped (it then has all of its owner's permissions). When the scopes
        can't be read, *org* is recorded so the probe notes its verdicts are
        role-only, and None is returned."""
        if client.access_token:
            self._unverified_scope_orgs.append(org)
            return None

        try:
            keys = await client.get_current_user_application_keys()
        except HTTPStatusError as error:
            logger.warning(
                "Could not read the application key's scopes "
                f"(HTTP {error.response.status_code}); checking the owner's role "
                "permissions only"
            )
            self._unverified_scope_orgs.append(org)
            return None

        last4 = client.dd_app_key[-4:]
        matches = [key for key in keys if key["attributes"].get("last4") == last4]
        if len(matches) != 1:
            logger.warning(
                f"Found {len(matches)} application keys of the current user ending "
                "with the configured key; checking the owner's role permissions only"
            )
            self._unverified_scope_orgs.append(org)
            return None
        return matches[0]["attributes"].get("scopes")

    async def _mark_checks(
        self, checks: list[ProbeCheck], status: ProbeCheckStatus, message: str
    ) -> None:
        for check in checks:
            check.status = status
            check.message = message
        await self.context.update_progress()
