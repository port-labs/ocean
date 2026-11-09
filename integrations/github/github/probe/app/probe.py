from typing import cast

import httpx
import jwt
from github.clients.auth.abstract_authenticator import GitHubAppToken
from github.helpers.api_error_messages import format_github_request_error
from github.helpers.exceptions import AuthenticationException
from github.probe.app.permissions import AppKindPermissionVerdict
from port_ocean.core.probe import KindPermissionVerdict, ProbeCheckStatus

from github.probe.base_probe_flow import GitHubPermissionProbeFlow, org_scopes

MISSING_PERMISSIONS_MESSAGE = (
    "Your app installation token is valid, but permission verification is not "
    "available because GitHub did not return installation permissions."
)

_APP_INVALID_CREDENTIALS_MESSAGE = (
    "GitHub App credentials are invalid. "
    "Please verify the GitHub App ID and private key are correct."
)


def format_app_probe_auth_error(
    error: BaseException,
    *,
    action: str = "Failed to fetch installation token",
) -> str:
    """Probe-only: turn auth/HTTP failures into indicative test-connection messages."""
    # Auth failures are either the error itself or wrapped once via `raise ... from`.
    root = error.__cause__ or error

    if isinstance(root, httpx.HTTPStatusError) and root.response is not None:
        if root.response.status_code == 401:
            return f"{action}: {_APP_INVALID_CREDENTIALS_MESSAGE}"
        return format_github_request_error(
            root.response,
            action=action,
            unauthorized_hint=_APP_INVALID_CREDENTIALS_MESSAGE,
        )

    if isinstance(root, jwt.PyJWTError) or isinstance(error, jwt.PyJWTError):
        return f"{action}: {_APP_INVALID_CREDENTIALS_MESSAGE}"

    message = str(error)
    if message.startswith(f"{action}:"):
        return message
    return f"{action}: {message}"


class GitHubAppPermissionProbe(GitHubPermissionProbeFlow):
    @property
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        return AppKindPermissionVerdict

    async def _fail_org_checks(self, organization: str, message: str) -> None:
        checks = await self.context.add_scopes(
            *org_scopes([organization])  # type: ignore[arg-type]
        )
        for check in checks:
            check.status = ProbeCheckStatus.FAILURE
            check.message = message

        await self.context.update_progress()

    async def run(self) -> None:
        for authenticator in self.authenticators:
            if authenticator.organization is None:
                continue

            try:
                token = cast(GitHubAppToken, await authenticator.get_token())
            except AuthenticationException as error:
                await self._fail_org_checks(
                    authenticator.organization,
                    format_app_probe_auth_error(error),
                )
                continue

            if token.permissions is None:
                await self._fail_org_checks(
                    authenticator.organization, MISSING_PERMISSIONS_MESSAGE
                )
                continue

            checks = await self.context.add_scopes(
                *org_scopes([authenticator.organization])  # type: ignore[arg-type]
            )

            await self._resolve_checks(checks, token.permissions or {})
