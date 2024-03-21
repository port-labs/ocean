import asyncio
import typing
from typing import Any, Dict
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.clients.port.types import UserAgentType
from azure_devops.webhooks.webhook_event import WebhookEvent
from azure_devops.misc import extract_branch_name_from_ref
from .listener import HookListener
from azure_devops.misc import GitPortAppConfig
from azure_devops.gitops.generate_entities import generate_entities_from_commit_id
from azure_devops.misc import Kind


class PushHookListener(HookListener):
    webhook_events = [WebhookEvent(publisherId="tfs", eventType="git.push")]

    async def on_hook(self, data: Dict[str, Any]) -> None:
        config: GitPortAppConfig = typing.cast(GitPortAppConfig, event.port_app_config)
        push_url = data["resource"]["url"]
        push_params = {"includeRefUpdates": True}
        push_data = (
            await self._client.send_request("GET", push_url, params=push_params)
        ).json()
        updates: list[dict[str, Any]] = push_data["refUpdates"]

        ref_update_tasks = []
        for update in updates:
            task = asyncio.create_task(self.process_ref_update(config, update))
            ref_update_tasks.append(task)

        await asyncio.gather(*ref_update_tasks, self.register_repository(push_data))

    async def process_ref_update(
        self, config: GitPortAppConfig, update: Dict[str, Any]
    ) -> None:
        repo_id = update["repositoryId"]
        branch = extract_branch_name_from_ref(update["name"])
        old_commit = update["oldObjectId"]
        new_commit = update["newObjectId"]
        if config.branch == branch:
            new_entities = await generate_entities_from_commit_id(
                self._client, config.spec_path, repo_id, new_commit
            )
            logger.info(f"Got {len(new_entities)} new entities")

            old_entities = await generate_entities_from_commit_id(
                self._client, config.spec_path, repo_id, old_commit
            )
            logger.info(f"Got {len(old_entities)} old entities")

            await ocean.update_diff(
                {"before": old_entities, "after": new_entities},
                UserAgentType.gitops,
            )

    async def register_repository(self, push_data: Dict[str, Any]) -> None:
        await ocean.register_raw(
            Kind.REPOSITORY,
            [await self._client.get_repository(push_data["repository"]["id"])],
        )
