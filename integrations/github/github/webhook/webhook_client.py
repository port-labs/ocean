from typing import Any, AsyncIterator

from github.webhook.base_webhook_client import BaseGithubWebhookClient, HookTarget


class GithubWebhookClient(BaseGithubWebhookClient):
    def __init__(
        self, *, organization: str, webhook_secret: str | None = None, **kwargs: Any
    ):
        """
        Initialize the GitHub organization webhook client.

        GitHub organization-scoped webhook client.

        This client manages webhooks at the organization level:
        - GET  /orgs/{org}/hooks
        - POST /orgs/{org}/hooks
        - PATCH /orgs/{org}/hooks/{hook_id}

        Args:
            organization: GitHub organization login.
            webhook_secret: Optional secret for authenticating incoming webhooks.
            **kwargs: Passed through to `GithubRestClient` (via `BaseGithubWebhookClient`).
        """
        super().__init__(webhook_secret=webhook_secret, **kwargs)
        self.organization = organization

    async def iter_hook_targets(self) -> AsyncIterator[HookTarget]:
        yield HookTarget(
            hooks_url=f"{self.base_url}/orgs/{self.organization}/hooks",
            single_hook_url_template=(
                f"{self.base_url}/orgs/{self.organization}/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": self.organization},
        )
