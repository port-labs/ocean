from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.utils import integration_config
from github.webhook.clients.base_webhook_client import BaseGithubWebhookClient
from github.webhook.clients.personal_account_webhook_client import (
    GithubPersonalAccountWebhookClient,
)
from github.webhook.clients.webhook_client import GithubWebhookClient


class GithubWebhookClientFactory:
    @staticmethod
    async def create(
        *,
        authenticator: AbstractGitHubAuthenticator,
        org_name: str,
        webhook_secret: str | None,
    ) -> BaseGithubWebhookClient:
        config = integration_config(authenticator)
        is_personal_org = await authenticator.is_personal_org(
            config["github_host"], org_name
        )

        client_cls = (
            GithubPersonalAccountWebhookClient
            if is_personal_org
            else GithubWebhookClient
        )
        return client_cls(
            **config,
            organization=org_name,
            webhook_secret=webhook_secret,
        )
