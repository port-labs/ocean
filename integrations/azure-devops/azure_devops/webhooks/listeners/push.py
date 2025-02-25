import asyncio
import typing
import json
import yaml
from typing import Any, Dict

from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from azure_devops.gitops.generate_entities import generate_entities_from_commit_id
from azure_devops.misc import GitPortAppConfig, Kind, extract_branch_name_from_ref
from azure_devops.webhooks.webhook_event import WebhookEvent
from azure_devops.client.file_processing import parse_content

from .listener import HookListener


class PushHookListener(HookListener):
    webhook_events = [WebhookEvent(publisherId="tfs", eventType="git.push")]

    async def on_hook(self, data: Dict[str, Any]) -> None:
        logger.debug(f"Got push event with initial data {data}")
        config: GitPortAppConfig = typing.cast(GitPortAppConfig, event.port_app_config)
        push_url = data["resource"]["url"]
        push_params = {"includeRefUpdates": True}
        push_data = (
            await self._client.send_request("GET", push_url, params=push_params)
        ).json()
        updates: list[dict[str, Any]] = push_data["refUpdates"]

        ref_update_tasks = []
        for update in updates:
            branch = extract_branch_name_from_ref(update["name"])
            if config.use_default_branch:
                # The repository's default branch is not included in the ref updates
                # but is in the initial data from the webhook event from the path
                # `resource.repository.defaultBranch`
                default_branch_with_ref: str = data["resource"]["repository"][
                    "defaultBranch"
                ]
                default_branch = extract_branch_name_from_ref(default_branch_with_ref)
            else:
                default_branch = config.branch

            if branch != default_branch:
                logger.info("Skipping ref update for non-default branch")
                continue
            task = asyncio.create_task(self.process_ref_update(config, update))
            ref_update_tasks.append(task)

        if not ref_update_tasks:
            logger.info("No ref updates to process")
            return

        logger.debug(f"Created {len(ref_update_tasks)} tasks for processing updates")

        await asyncio.gather(*ref_update_tasks, self.register_repository(push_data))

    async def process_ref_update(
        self,
        config: GitPortAppConfig,
        update: Dict[str, Any],
    ) -> None:
        logger.info(f"Processing ref update with update: {update}")
        repo_id = update["repositoryId"]
        old_commit = update["oldObjectId"]
        new_commit = update["newObjectId"]

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

        await self.sync_changed_files_in_commit(repo_id, new_commit)

    async def sync_changed_files_in_commit(self, repo_id: str, commit_id: str) -> None:
        """Fetches changed files from a commit and ingests them into Port."""
        logger.info(f"Fetching file changes for commit {commit_id}")

        try:
            repo_info = await self._client.get_repository(repo_id)
            project_id = repo_info["project"]["id"]

            # Get file changes from commit
            url = f"{self._client._organization_base_url}/{project_id}/_apis/git/repositories/{repo_id}/commits/{commit_id}/changes"
            response = await self._client.send_request(
                "GET", url, params={"api-version": "7.1"}
            )
            changes = response.json().get("changes", [])

            for change in changes:
                file_path = change.get("item", {}).get("path", "")
                if file_path.endswith((".yaml", ".yml", ".json")):
                    await self.ingest_file_to_port(repo_info, commit_id, file_path)

        except Exception as e:
            logger.error(f"Error fetching file changes: {e}")

    async def ingest_file_to_port(
        self,
        repo_info: dict[str, Any],
        commit_id: str,
        file_path: str,
    ) -> None:
        """Retrieves, parses, and registers a file with Port."""
        logger.info(f"Ingesting file {file_path} to Port")
        try:
            file_content = await self._client.get_file_by_commit(
                file_path, repo_info["id"], commit_id
            )
            if not file_content:
                logger.warning(f"No content found for file {file_path}")
                return

            # Use the existing parse_content function
            parsed_content = await parse_content(file_content)
            
            # Only proceed if the file is a structured format we can parse
            if file_path.endswith((".yaml", ".yml", ".json")):
                file_data = {
                    "file": {
                        "path": file_path,
                        "content": {"raw": file_content.decode("utf-8"), "parsed": parsed_content},
                        "link": f"{repo_info['webUrl']}/blob/{commit_id}/{file_path.lstrip('/')}",
                        "size": len(file_content),
                    },
                    "repo": repo_info,
                }
                await ocean.register_raw(Kind.FILE, [file_data])
                logger.info(f"Successfully ingested file {file_path} to Port")

        except Exception as e:
            logger.error(f"Error ingesting file {file_path}: {e}")

    async def register_repository(self, push_data: Dict[str, Any]) -> None:
        await ocean.register_raw(
            Kind.REPOSITORY,
            [await self._client.get_repository(push_data["repository"]["id"])],
        )
