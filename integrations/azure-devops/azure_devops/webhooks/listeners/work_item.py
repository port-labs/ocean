from typing import Any
from azure_devops.webhooks.webhook_event import WebhookEvent
from port_ocean.context.ocean import ocean
from .listener import HookListener


class WorkItemHookListener(HookListener):
    webhook_events = [
        WebhookEvent(publisherId="tfs", eventType="workitem.created"),
        WebhookEvent(publisherId="tfs", eventType="workitem.deleted"),
        WebhookEvent(publisherId="tfs", eventType="workitem.updated"),
    ]

    async def on_hook(self, data: dict[str, Any]) -> None:
        work_item_id = data["resource"]["id"]
        work_item_data = await self._client.get_work_item(work_item_id)
        await ocean.register_raw("work_item", [work_item_data])
