from typing import Any, cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.pull_request_comment_exporter import (
    RestPullRequestCommentExporter,
)
from github.core.exporters.pull_request_exporter import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
from github.core.options import SinglePullRequestOptions
from github.helpers.utils import GithubClientType, ObjectKind
from github.webhook.events import (
    PULL_REQUEST_COMMENT_EVENTS,
    PULL_REQUEST_REVIEW_EVENTS,
)
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from integration import GithubPullRequestConfig


class PullRequestCommentWebhookProcessor(BaseRepositoryWebhookProcessor):
    """Refresh a pull request's ``__comments`` when comment-related events fire.

    Matching kind is ``pull-request`` (not a dedicated comment kind). Only runs
    when ``includeComments`` is true. Never deletes the pull request because a
    comment changed.
    """

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
        return [ObjectKind.PULL_REQUEST]

    def _parent_pull_request(
        self, payload: EventPayload, header: str | None
    ) -> dict[str, Any]:
        if header == "issue_comment":
            return payload["issue"]
        return payload["pull_request"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        empty = WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
        config = cast(GithubPullRequestConfig, resource_config)
        if not config.selector.include_comments:
            return empty

        header = self.event.headers.get("x-github-event")
        parent = self._parent_pull_request(payload, header)
        repo = payload["repository"]
        repo_name = repo["name"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        pr_number = parent["number"]
        action = payload["action"]

        logger.info(
            f"Processing {header} {action} for comments on "
            f"{organization}/{repo_name}#{pr_number}"
        )

        if not await self.should_process_repo_search(payload, resource_config):
            return empty

        is_graphql_api = config.selector.api == GithubClientType.GRAPHQL
        pr_exporter = (
            GraphQLPullRequestExporter(
                await create_github_client_for_org(
                    organization, GithubClientType.GRAPHQL
                )
            )
            if is_graphql_api
            else RestPullRequestExporter(
                await create_github_client_for_org(organization)
            )
        )
        data_to_upsert = await pr_exporter.get_resource(
            SinglePullRequestOptions(
                organization=organization,
                repo_name=repo_name,
                pr_number=pr_number,
                repo=repo if is_graphql_api else None,
                enrich_with_first_commit=config.selector.enrich_with_first_commit,
                exclude_graphql_fields=config.selector.exclude_graphql_fields,
            )
        )
        if not data_to_upsert:
            logger.warning(
                f"No pull request data for {organization}/{repo_name}#{pr_number}; "
                "skipping comments refresh"
            )
            return empty

        comment_exporter = RestPullRequestCommentExporter(
            await create_github_client_for_org(organization)
        )
        enriched = await comment_exporter.enrich_pull_requests(
            [data_to_upsert],
            organization=organization,
            include_comments=config.selector.include_comments,
            include_review_stats=config.selector.include_review_stats,
            bot_logins=list(config.selector.bot_logins),
        )
        data_to_upsert = enriched[0]

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
