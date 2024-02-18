import typing
from typing import Any
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.clients.port.types import UserAgentType
from azure_devops.webhooks.webhook_event import WebhookEvent
from .listener import HookListener
from azure_devops.gitops.port_app_config import GitPortAppConfig
from azure_devops.gitops.generate_entities import generate_entities_from_commit_id


class PushHookListener(HookListener):
    webhook_events = [WebhookEvent(publisherId="tfs", eventType="git.push")]

    async def on_hook(self, data: dict[str, Any]) -> None:
        logger.info("Got Push event!")
        config: GitPortAppConfig = typing.cast(GitPortAppConfig, event.port_app_config)

        push_url = data["resource"]["url"]
        push_params = {"includeRefUpdates": True}
        push_data = (
            await self._client.send_get_request(push_url, params=push_params)
        ).json()

        updates = push_data["refUpdates"]
        for update in updates:
            repo_id = update["repositoryId"]
            branch = "/".join(
                update["name"].split("/")[2:]
            )  # Remove /refs/heads from ref to get branch
            old_commit = update["oldObjectId"]
            new_commit = update["newObjectId"]
            if config.branch == branch:
                new_entities = generate_entities_from_commit_id(
                    self._client, config.spec_path, repo_id, new_commit
                )
                logger.debug(f"Got {len(new_entities)} new entities")

                old_entities = generate_entities_from_commit_id(
                    self._client, config.spec_path, repo_id, old_commit
                )
                logger.debug(f"Got {len(old_entities)} old entities")

                await ocean.update_diff(
                    {"before": old_entities, "after": new_entities},
                    UserAgentType.gitops,
                )

            await ocean.register_raw(
                "repository",
                [await self._client.get_repository(push_data["repository"]["id"])],
            )
