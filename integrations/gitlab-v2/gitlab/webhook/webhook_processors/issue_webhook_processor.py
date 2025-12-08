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

        object_attrs: dict[str, Any] = payload["object_attributes"]
        selector = cast(GitlabIssueResourceConfig, resource_config).selector
        should_process = self._should_process_issue(selector, object_attrs)

        if not should_process:
            logger.info(
                f"Issue {issue_id} filtered out by selector criteria. Skipping..."
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
        return (
            self._check_state_filter(selector, object_attrs)
            and self._check_issue_type_filter(selector, object_attrs)
            and self._check_labels_filter(selector, object_attrs)
        )

    def _check_state_filter(
        self, selector: IssueSelector, object_attrs: dict[str, Any]
    ) -> bool:
        if not selector.state:
            return True

        has_desired_state = object_attrs["state"] == selector.state
        if not has_desired_state:
            logger.info(
                f"Issue {object_attrs['iid']} state '{object_attrs['state']}' does not match selector state '{selector.state}'"
            )
        return has_desired_state

    def _check_issue_type_filter(
        self, selector: IssueSelector, object_attrs: dict[str, Any]
    ) -> bool:
        if not selector.issue_type:
            return True

        has_desired_issue_type = (
            object_attrs["type"].lower() == selector.issue_type.lower()
        )
        if not has_desired_issue_type:
            logger.info(
                f"Issue {object_attrs['iid']} type '{object_attrs['type']}' does not match selector type '{selector.issue_type}'"
            )
        return has_desired_issue_type

    def _check_labels_filter(
        self, selector: IssueSelector, object_attrs: dict[str, Any]
    ) -> bool:
        if not selector.labels:
            return True

        required_labels = {label.strip() for label in selector.labels.split(",")}
        issue_label_titles = {label["title"] for label in object_attrs["labels"]}
        has_desired_labels_filter = required_labels.issubset(issue_label_titles)
        if not has_desired_labels_filter:
            logger.info(
                f"Issue {object_attrs.get('iid')} labels {issue_label_titles} do not match selector labels '{selector.labels}'"
            )
        return has_desired_labels_filter
