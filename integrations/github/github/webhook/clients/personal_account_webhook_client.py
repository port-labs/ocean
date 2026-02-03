from typing import Any, AsyncIterator, cast

from github.webhook.clients.base_webhook_client import (
    BaseGithubWebhookClient,
    HookTarget,
)
from github.clients.auth.github_app_authenticator import GitHubAppAuthenticator
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

UNSUPPORTED_REPO_EVENTS = {"organization", "team", "membership", "member"}


class GithubPersonalAccountWebhookClient(BaseGithubWebhookClient):
    """
    Initialize the GitHub repository webhook client.

    GitHub repository-scoped webhook client.

    This client manages webhooks at the repository level:
    - GET  /repos/{owner}/{repo}/hooks
    - POST /repos/{owner}/{repo}/hooks
    - PATCH /repos/{owner}/{repo}/hooks/{hook_id}

    Args:
        webhook_secret: Optional secret for authenticating incoming webhooks.
        **kwargs: Passed through to `GithubRestClient` (via `BaseGithubWebhookClient`).
    """

    def get_supported_events(self) -> list[str]:
        return [e for e in WEBHOOK_CREATE_EVENTS if e not in UNSUPPORTED_REPO_EVENTS]

    async def _iter_owned_repositories(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Iterate over batches of repositories owned by the authenticated user.

        Yields lists of repository dicts as returned by GitHub's REST API.
        """

        if isinstance(self.authenticator, GitHubAppAuthenticator):
            async for page in self.send_paginated_request(
                f"{self.base_url}/installation/repositories",
            ):
                response = cast(dict[str, list[dict[str, Any]]], page)
                yield response["repositories"]
            return

        async for repos in self.send_paginated_request(
            f"{self.base_url}/user/repos",
            {"affiliation": "owner"},
        ):
            yield repos

    async def iter_hook_targets(self) -> AsyncIterator[HookTarget]:
        async for repos in self._iter_owned_repositories():
            for repo in repos:
                owner = repo["owner"]["login"]
                repo_name = repo["name"]

                yield HookTarget(
                    hooks_url=f"{self.base_url}/repos/{owner}/{repo_name}/hooks",
                    single_hook_url_template=(
                        f"{self.base_url}/repos/{owner}/{repo_name}/hooks/{{webhook_id}}"
                    ),
                    log_scope={
                        "organization": self.organization,
                        "repository": repo_name,
                    },
                    target_type="repository",
                )
