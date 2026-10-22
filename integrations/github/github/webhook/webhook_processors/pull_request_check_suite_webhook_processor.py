from typing import Any, cast

from loguru import logger

from github.helpers.utils import ObjectKind
from github.webhook.events import CHECK_SUITE_PR_REFRESH_EVENTS
from github.webhook.webhook_processors.base_pull_request_webhook_processor import (
    BasePullRequestWebhookProcessor,
)
from integration import GithubPullRequestConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class PullRequestCheckSuiteWebhookProcessor(BasePullRequestWebhookProcessor):
    """Refresh pull requests when a check suite completes so checksStatus stays current."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if event.headers.get("x-github-event") != "check_suite":
            return False
        return event.payload.get("action") in CHECK_SUITE_PR_REFRESH_EVENTS

    async def _validate_payload(self, payload: EventPayload) -> bool:
        check_suite = payload.get("check_suite")
        return isinstance(check_suite, dict)

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        check_suite = payload["check_suite"]
        repo = payload["repository"]
        repo_name = repo["name"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubPullRequestConfig, resource_config)

        pull_requests = check_suite.get("pull_requests") or []
        if not pull_requests:
            logger.debug(
                f"Check suite {action} for {organization}/{repo_name} has no linked "
                "pull requests; skipping pull-request refresh"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []
        for pull_request in pull_requests:
            number = pull_request.get("number")
            if not number:
                continue
            result = await super().handle_event(
                {
                    **payload,
                    "action": action,
                    "pull_request": {"number": number},
                },
                config,
            )
            updated.extend(result.updated_raw_results)
            deleted.extend(result.deleted_raw_results)

        logger.info(
            f"Processed check suite {action} for {organization}/{repo_name}: "
            f"updated={len(updated)} deleted={len(deleted)}"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated, deleted_raw_results=deleted
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]
