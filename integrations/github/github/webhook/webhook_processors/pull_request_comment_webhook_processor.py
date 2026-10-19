from typing import Any, cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.core.exporters.pull_request_comment_exporter import (
    CommentType,
    normalize_pull_request_comment,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import (
    PULL_REQUEST_COMMENT_EVENTS,
    PULL_REQUEST_REVIEW_EVENTS,
)
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from integration import GithubPullRequestCommentConfig


def _comment_source(
    payload: EventPayload,
) -> tuple[str, dict[str, Any], CommentType] | None:
    """Return the header event, raw comment, and normalized type for this payload."""
    header = payload.get("__github_event")
    if header == "issue_comment" and "pull_request" in payload.get("issue", {}):
        return header, payload["comment"], "comment"
    if header == "pull_request_review_comment":
        return header, payload["comment"], "review"
    if header == "pull_request_review":
        return header, payload["review"], "review-summary"
    return None


class PullRequestCommentWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        if payload.get("action") not in (
            *PULL_REQUEST_COMMENT_EVENTS,
            *PULL_REQUEST_REVIEW_EVENTS,
        ):
            return False
        if "comment" in payload:
            return isinstance(payload["comment"], dict) and "id" in payload["comment"]
        review = payload.get("review")
        return isinstance(review, dict) and "id" in review

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        header = event.headers.get("x-github-event")
        action = event.payload.get("action")
        if header == "issue_comment":
            return (
                action in PULL_REQUEST_COMMENT_EVENTS
                and "pull_request" in event.payload.get("issue", {})
            )
        if header == "pull_request_review_comment":
            return action in PULL_REQUEST_COMMENT_EVENTS and "comment" in event.payload
        if header == "pull_request_review":
            return action in PULL_REQUEST_REVIEW_EVENTS and "review" in event.payload
        return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST_COMMENT]

    def _parent_pull_request(
        self, payload: EventPayload, header: str
    ) -> dict[str, Any]:
        if header == "issue_comment":
            return payload["issue"]
        return payload["pull_request"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        header = self.event.headers.get("x-github-event")
        payload_with_header = {**payload, "__github_event": header}
        source = _comment_source(payload_with_header)
        if source is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        event_name, raw_comment, comment_type = source
        parent = self._parent_pull_request(payload, event_name)
        repo = payload["repository"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubPullRequestCommentConfig, resource_config)
        action = payload["action"]

        logger.info(
            f"Processing {event_name} {action} on {organization}/{repo['name']}#{parent.get('number')}"
        )

        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        normalized = normalize_pull_request_comment(
            raw_comment,
            organization=organization,
            repo_name=repo["name"],
            pull_request_id=parent["id"],
            pull_request_number=parent["number"],
            comment_type=comment_type,
        )
        state = parent.get("state")
        tracked = state in config.selector.states
        drop = (
            action in ("deleted", "dismissed")
            or not tracked
            or (
                comment_type == "review-summary"
                and not (raw_comment.get("body") or "").strip()
            )
        )
        if drop:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[normalized]
            )
        return WebhookEventRawResults(
            updated_raw_results=[normalized], deleted_raw_results=[]
        )
