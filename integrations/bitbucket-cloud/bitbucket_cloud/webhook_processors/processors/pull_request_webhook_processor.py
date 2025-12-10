from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.webhook_processors.events import PullRequestEvents
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    _BitbucketAbstractWebhookProcessor,
)
from integration import PullRequestResourceConfig
from typing import cast, Any
from bitbucket_cloud.utils import build_repo_params
from bitbucket_cloud.webhook_processors.options import PullRequestSelectorOptions


class PullRequestWebhookProcessor(_BitbucketAbstractWebhookProcessor):

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        try:
            return bool(PullRequestEvents(event.headers["x-event-key"]))
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        raw_pull_request = payload["pullrequest"]
        pull_request_id = raw_pull_request["id"]
        repository_id = payload["repository"]["uuid"]
        logger.info(
            f"Handling pull request webhook event for repository: {repository_id} and pull request: {pull_request_id}"
        )
        selector = cast(PullRequestResourceConfig, resource_config).selector
        options: PullRequestSelectorOptions = PullRequestSelectorOptions(
            user_role=selector.user_role,
            repo_query=selector.repo_query,
            pull_request_query=selector.pull_request_query,
        )

        if not await self._check_repository_filter(
            payload["repository"]["uuid"], options
        ):
            logger.info(
                f"Pull request repository {payload['repository']['name']} does not match any of the repository filters in the selector: {options}. Skipping..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        pull_request_details = await self._webhook_client.get_pull_request(
            repository_id, pull_request_id
        )
        return WebhookEventRawResults(
            updated_raw_results=[pull_request_details],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        required_fields = ["repository", "pullrequest"]
        return all(field in payload for field in required_fields)

    async def _check_repository_filter(
        self, repo_uuid: str, options: PullRequestSelectorOptions
    ) -> bool:
        """
        Check if the repository matches the repository filter.
        """
        user_role = options["user_role"]
        repo_query = options["repo_query"]
        if not user_role and not repo_query:
            return True

        params: dict[str, Any] = build_repo_params(user_role, repo_query)
        uuid_query = f'uuid="{repo_uuid}"'
        params["q"] = (
            f"({params['q']}) AND {uuid_query}" if "q" in params else uuid_query
        )
        logger.info(f"Repository filter check with params: {params}")

        async for repositories in self._webhook_client.get_repositories(params=params):
            # returns a list containing only the repository if it matches the filter
            if repositories:
                return True
        return False
