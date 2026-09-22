from abc import ABC
from typing import Any

from initialize_client import get_or_create_jira_client
from jira.actions.utils import get_issue_browse_url
from jira.client import JiraClient
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun


class AbstractJiraExecutor(AbstractExecutor, ABC):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self._client: JiraClient | None = None

    @property
    def client(self) -> JiraClient:
        if self._client is None:
            self._client = get_or_create_jira_client()
        return self._client

    @client.setter
    def client(self, value: JiraClient) -> None:
        self._client = value

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0

    async def _complete_issue_action(
        self,
        run: IntegrationRun,
        *,
        issue_key: str,
        message: str,
        status_label: str,
        output: dict[str, Any],
    ) -> None:
        issue_url = (
            get_issue_browse_url(
                self.client.jira_url,
                issue_key,
                oauth_enabled=self.client.is_oauth_enabled(),
            )
            or ""
        )
        if issue_url:
            message = f"{message}: {issue_url}"

        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "issueKey": issue_key,
                "issueUrl": issue_url,
                **output,
            }

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label=status_label,
        )
