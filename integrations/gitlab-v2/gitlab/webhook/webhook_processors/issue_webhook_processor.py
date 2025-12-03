from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabIssueResourceConfig, IssueSelector
from typing import cast, Any


class IssueWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["issue"]
    hooks = ["Issue Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue_id = payload["object_attributes"]["iid"]
        project_id = payload["project"]["id"]
        logger.info(
            f"Handling issue webhook event for project {project_id} and issue {issue_id}"
        )

        object_attrs: dict[str, Any] = payload.get("object_attributes", {})
        selector = cast(GitlabIssueResourceConfig, resource_config).selector
        should_process = self._should_process_issue(selector, object_attrs)

        if not should_process:
            logger.info(
                f"Issue {issue_id} filtered out by selector criteria - skipping API call"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        issue = await self._gitlab_webhook_client.get_issue(project_id, issue_id)

        return WebhookEventRawResults(
            updated_raw_results=[issue],
            deleted_raw_results=[],
        )

    def _should_process_issue(
        self,
        selector: IssueSelector,
        object_attrs: dict[str, Any],
    ) -> bool:
        """Helper function to determine if an issue should be processed based on selector criteria."""
        should_process = True

        if selector.state and object_attrs.get("state") != selector.state:
            logger.info(
                f"Issue {object_attrs.get('iid')} state '{object_attrs.get('state')}' does not match selector state '{selector.state}'"
            )
            should_process = False

        if selector.issue_type and should_process:
            webhook_type = object_attrs.get("type", "").lower()
            if webhook_type != selector.issue_type:
                logger.info(
                    f"Issue {object_attrs.get('iid')} type '{webhook_type}' does not match selector type '{selector.issue_type}'"
                )
                should_process = False

        if selector.labels and should_process:
            required_labels = {label.strip() for label in selector.labels.split(",")}
            issue_label_titles = {
                label.get("title", "") for label in object_attrs.get("labels", [])
            }
            if not required_labels.issubset(issue_label_titles):
                logger.info(
                    f"Issue {object_attrs.get('iid')} labels {issue_label_titles} do not contain all required labels {required_labels}"
                )
                should_process = False

        return should_process
