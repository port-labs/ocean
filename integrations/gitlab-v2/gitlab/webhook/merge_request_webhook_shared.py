from datetime import timezone
from typing import Any

from dateutil import parser
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from gitlab.clients.gitlab_client import GitLabClient
from integration import GitlabMergeRequestSelector


async def handle_merge_request_webhook_event(
    client: GitLabClient,
    selector: GitlabMergeRequestSelector,
    *,
    project_id: int,
    merge_request_iid: int,
    state: str,
    updated_at_raw: str | None,
    delete_payload: dict[str, Any],
    require_include_comments: bool = False,
    include_comments_override: bool | None = None,
) -> WebhookEventRawResults:
    """Shared upsert/delete path for merge-request and merge-request note webhooks."""
    if require_include_comments and not selector.include_comments:
        logger.debug("Skipping merge request note event; includeComments is false")
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    if state not in selector.states:
        logger.info(
            f"Deleting merge request {merge_request_iid} as current state {state} "
            f"does not match configured states {selector.states}."
        )
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[delete_payload],
        )

    if updated_at_raw and state != "opened":
        updated_at = parser.parse(updated_at_raw).replace(tzinfo=timezone.utc)
        if updated_at < selector.updated_after_datetime:
            logger.info(
                f"Deleting merge request {merge_request_iid} as updated at "
                f"{updated_at} is before {selector.updated_after_datetime}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[delete_payload],
            )

    include_comments = (
        include_comments_override
        if include_comments_override is not None
        else selector.include_comments
    )

    merge_request = await client.fetch_single_merge_request(
        project_id,
        merge_request_iid,
        enrich_with_commits=selector.enrich_with_commits,
        enrich_with_review_discussion=selector.enrich_with_review_discussion,
        include_comments=include_comments,
    )
    if not merge_request:
        logger.warning(
            f"Merge request {merge_request_iid} in project {project_id} "
            "was not found, skipping upsert"
        )
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

    return WebhookEventRawResults(
        updated_raw_results=[merge_request],
        deleted_raw_results=[],
    )
