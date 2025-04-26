from typing import cast
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    _BitbucketAbstractWebhookProcessor,
)
from integration import BitbucketFileResourceConfig
from bitbucket_cloud.helpers.file_kind_live_event import (
    process_file_changes,
)
from loguru import logger

YAML_SUFFIX = (".yaml", ".yml")
JSON_SUFFIX = ".json"


class FileWebhookProcessor(_BitbucketAbstractWebhookProcessor):

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        try:
            return event.headers.get("x-event-key") == "repo:push"
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FILE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repository = payload["repository"]["uuid"]
        repo_name = payload["repository"]["name"].replace(" ", "-")
        matching_resource_config = cast(BitbucketFileResourceConfig, resource_config)
        selector = matching_resource_config.selector
        skip_parsing = selector.files.skip_parsing
        tracked_repository = selector.files.repos
        if tracked_repository and repo_name not in tracked_repository:
            logger.info(
                f"Skipping push event for repository {repo_name} because it is not in {tracked_repository}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        updated_raw_results, deleted_raw_results = await process_file_changes(
            repository=repository,
            changes=payload["push"]["changes"],
            selector=selector,
            skip_parsing=skip_parsing,
            webhook_client=self._webhook_client,
            payload=payload,
        )

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        required_fields = ["repository", "push"]
        return all(field in payload for field in required_fields)
