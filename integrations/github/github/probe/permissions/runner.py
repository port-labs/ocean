import httpx

from port_ocean.core.probe import ProbeContext

from github.clients.auth import get_auth_provider
from github.helpers.exceptions import AuthenticationException
from github.probe.permissions.app import GitHubAppPermissionProbe
from github.probe.permissions.pat import GitHubPatPermissionProbe

UNAUTHORIZED_STATUS_CODES = (
    httpx.codes.UNAUTHORIZED,
    httpx.codes.FORBIDDEN,
)


class GitHubPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context

    async def run(self) -> None:
        try:
            provider = get_auth_provider()
            authenticators = await provider.list_authenticators()
            flow = (
                GitHubAppPermissionProbe(self.context, authenticators)
                if provider.is_app_auth()
                else GitHubPatPermissionProbe(self.context, authenticators)
            )
            await flow.run()
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            self.context.fail(_lookup_failure_message(error))
        except AuthenticationException as error:
            cause = error.__cause__
            if isinstance(cause, (httpx.HTTPStatusError, httpx.RequestError)):
                self.context.fail(_lookup_failure_message(cause))
            else:
                self.context.fail(str(error))


def _lookup_failure_message(
    error: httpx.HTTPStatusError | httpx.RequestError,
) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code in UNAUTHORIZED_STATUS_CODES:
            return f"GitHub rejected the configured credentials with HTTP {status_code}"
        return f"GitHub returned HTTP {status_code} while probing permissions"

    return f"GitHub could not be reached while probing permissions: {error}"
