from typing import Any

from port_ocean.context.ocean import ocean
from azure_devops.webhooks.webhook_event import WebhookEvent
from .listener import HookListener


class PullRequestHookListener(HookListener):
    webhook_events = [
        WebhookEvent(publisherId="tfs", eventType="git.pullrequest.updated"),
        WebhookEvent(publisherId="tfs", eventType="git.pullrequest.created"),
    ]

    async def on_hook(self, data: dict[str, Any]) -> None:
        pull_request_id = data["resource"]["pullRequestId"]
        pull_request_data = await self._client.get_pull_request(pull_request_id)
        await ocean.register_raw("pull_request", [pull_request_data])
