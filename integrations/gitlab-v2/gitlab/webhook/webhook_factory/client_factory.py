from gitlab.clients.gitlab_client import GitLabClient
from gitlab.webhook.webhook_factory.group_webhook_factory import GroupWebHook
from gitlab.webhook.webhook_factory.project_webhook_factory import ProjectWebHook


class GitlabWebhookFactory:
    @staticmethod
    async def create_webhooks_for_namespace(
        client: GitLabClient,
        base_url: str,
        namespace: str,
    ) -> None:
        if await client.is_personal_namespace(namespace):
            await ProjectWebHook(
                client, base_url
            ).create_webhooks_for_personal_projects()
        else:
            group = await client.get_group(namespace)
            await GroupWebHook(client, base_url).create_group_webhook(group["id"])
