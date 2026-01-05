from typing import Any, AsyncIterator, Dict, List, Optional

from github.webhook.clients.base_webhook_client import (
    BaseGithubWebhookClient,
    HookTarget,
)
from github.webhook.events import WEBHOOK_CREATE_EVENTS


class GithubPersonalAccountWebhookClient(BaseGithubWebhookClient):
    def __init__(
        self,
        *,
        organization: str,
        webhook_secret: str | None = None,
        **kwargs: Any,
    ):
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
        super().__init__(webhook_secret=webhook_secret, **kwargs)
        self.organization = organization

    def get_supported_events(self) -> list[str]:
        disallowed_for_repo = {"organization", "team", "membership", "member"}
        return [e for e in WEBHOOK_CREATE_EVENTS if e not in disallowed_for_repo]

    async def _iter_owned_repositories(self) -> "Optional[List[Dict[str, Any]]]":
        """
        Fetch a batch of repositories owned by the authenticated user.

        Returns a list of repository dicts as returned by GitHub's REST API.
        """
        async for repos in self.send_paginated_request(
            f"{self.base_url}/user/repos",
            {"affiliation": "owner"},
        ):
            return repos
        return None

    async def iter_hook_targets(self) -> AsyncIterator[HookTarget]:

        async for repos in self.send_paginated_request(
            f"{self.base_url}/user/repos",
            {"affiliation": "owner"},
        ):
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
                )
