from typing import List
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults, EventPayload, EventHeaders
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import cast

from github.client import GitHubClient
from initialize_client import create_github_client
from integration import FileResourceConfig
from utils import ObjectKind

class FileWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("X-GitHub-Event") == "push"

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return [ObjectKind.FILE]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        signature = headers.get("X-Hub-Signature-256")
        if signature:
            return create_github_client().verify_webhook_signature(payload, signature)
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "ref" in payload and "commits" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        selector = cast(FileResourceConfig, resource_config).selector
        client = create_github_client()
        repo = payload["repository"]["full_name"]
        repo_id = payload["repository"]["id"]
        default_branch = payload["repository"]["default_branch"]
        if not payload["ref"].startswith(f"refs/heads/{default_branch}"):
            logger.info("Push not on default branch; skipping.")
            return WebhookEventRawResults([], [])
        updated = []
        deleted = []
        paths_to_fetch = set()
        for commit in payload.get("commits", []):
            for path in commit.get("added", []) + commit.get("modified", []):
                if (not selector.extensions or any(path.endswith(ext) for ext in selector.extensions)) and (
                    not selector.paths or any(path.startswith(p) for p in selector.paths)
                ):
                    paths_to_fetch.add(path)
            for path in commit.get("removed", []):
                if (not selector.extensions or any(path.endswith(ext) for ext in selector.extensions)) and (
                    not selector.paths or any(path.startswith(p) for p in selector.paths)
                ):
                    deleted.append({"repository_id": repo_id, "path": path})
        if paths_to_fetch:
            tasks = [client.get_file_content(repo, path) for path in paths_to_fetch]
            fetched = await asyncio.gather(*tasks, return_exceptions=True)
            updated = [f for f in fetched if not isinstance(f, Exception) and f]
            for f in updated:
                f["repository_id"] = repo_id
        return WebhookEventRawResults(updated, deleted)
