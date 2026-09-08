import httpx
from loguru import logger
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from typing import Any

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import ChangeIssueStatusError
from jira.actions.utils import get_issue_browse_url


class ChangeIssueStatusInput(AbstractJiraActionInput):
    issue_key: str = Field(..., alias="issueKey", min_length=1)
    status: str = Field(..., min_length=1)


class ChangeIssueStatusExecutor(AbstractJiraExecutor):
    ACTION_NAME = "change_issue_status"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_key = run.execution_properties.get("issueKey")
        return str(issue_key) if issue_key else None

    async def execute(self, run: IntegrationRun) -> None:
        action_input = ChangeIssueStatusInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Changing status of {action_input.issue_key} to {action_input.status}",
            status_label="Changing status",
            should_raise=False,
        )

        try:
            issue = await self.client.get_single_issue(
                action_input.issue_key, fields="status"
            )
        except httpx.HTTPStatusError as error:
            raise ChangeIssueStatusError.from_response(
                error.response,
                f"Could not load issue '{action_input.issue_key}'",
            )

        current_status = self._get_issue_status_name(issue)
        if current_status and self._normalize_status_name(
            current_status
        ) == self._normalize_status_name(action_input.status):
            message = (
                f"Issue {action_input.issue_key} is already in status "
                f"'{current_status}'"
            )
            await self._complete_run(run, action_input, current_status, message)
            return

        try:
            transitions = await self.client.get_issue_transitions(
                action_input.issue_key
            )
        except httpx.HTTPStatusError as error:
            raise ChangeIssueStatusError.from_response(
                error.response,
                f"Could not load transitions for issue '{action_input.issue_key}'",
            )

        transition_id = self._find_transition_id_for_status(
            transitions, action_input.status
        )
        if not transition_id:
            available_statuses = self._get_available_transition_statuses(transitions)
            available_statuses_text = (
                ", ".join(available_statuses) if available_statuses else "none"
            )
            raise ChangeIssueStatusError(
                f"No transition found to status '{action_input.status}' for issue "
                f"'{action_input.issue_key}'. Available target statuses: "
                f"{available_statuses_text}"
            )

        try:
            await self.client.transition_issue(action_input.issue_key, transition_id)
        except httpx.HTTPStatusError as error:
            raise ChangeIssueStatusError.from_response(
                error.response,
                f"Could not change status of issue '{action_input.issue_key}'",
            )

        message = (
            f"Changed issue {action_input.issue_key} to status "
            f"'{action_input.status}'"
        )
        await self._complete_run(run, action_input, action_input.status, message)
        logger.info(
            "Changed Jira issue status",
            issue_key=action_input.issue_key,
            status=action_input.status,
            transition_id=transition_id,
        )

    async def _complete_run(
        self,
        run: IntegrationRun,
        action_input: ChangeIssueStatusInput,
        status: str,
        message: str,
    ) -> None:
        issue_link = get_issue_browse_url(
            self.client.jira_url,
            action_input.issue_key,
            oauth_enabled=self.client.is_oauth_enabled(),
        )
        if issue_link:
            message = f"{message}: {issue_link}"

        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "issueKey": action_input.issue_key,
                "status": status,
                "issueUrl": issue_link or "",
            }

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Status changed",
        )

    @staticmethod
    def _normalize_status_name(status: str) -> str:
        return status.casefold().strip()

    @staticmethod
    def _get_issue_status_name(issue: dict[str, Any]) -> str | None:
        fields = issue.get("fields")
        if not isinstance(fields, dict):
            return None
        status = fields.get("status")
        if not isinstance(status, dict):
            return None
        status_name = status.get("name")
        return status_name if isinstance(status_name, str) else None

    @classmethod
    def _find_transition_id_for_status(
        cls, transitions_response: dict[str, Any], target_status: str
    ) -> str | None:
        normalized_target = cls._normalize_status_name(target_status)
        transitions = transitions_response.get("transitions")
        if not isinstance(transitions, list):
            return None

        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            to_status = transition.get("to")
            if not isinstance(to_status, dict):
                continue
            to_status_name = to_status.get("name")
            if (
                isinstance(to_status_name, str)
                and cls._normalize_status_name(to_status_name) == normalized_target
            ):
                transition_id = transition.get("id")
                if transition_id is not None:
                    return str(transition_id)
        return None

    @staticmethod
    def _get_available_transition_statuses(
        transitions_response: dict[str, Any],
    ) -> list[str]:
        statuses: list[str] = []
        seen: set[str] = set()
        transitions = transitions_response.get("transitions")
        if not isinstance(transitions, list):
            return statuses

        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            to_status = transition.get("to")
            if not isinstance(to_status, dict):
                continue
            to_status_name = to_status.get("name")
            if isinstance(to_status_name, str) and to_status_name not in seen:
                seen.add(to_status_name)
                statuses.append(to_status_name)
        return statuses
