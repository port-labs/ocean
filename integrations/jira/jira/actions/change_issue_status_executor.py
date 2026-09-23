from typing import Any

import httpx
from loguru import logger
from pydantic import Field, ValidationError
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import ChangeIssueStatusError
from jira.api_models import JiraIssueTransition, JiraIssueTransitionsResponse


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
            await self._complete_issue_action(
                run,
                issue_key=action_input.issue_key,
                message=(
                    f"Issue {action_input.issue_key} is already in status "
                    f"'{current_status}'"
                ),
                status_label="Status changed",
                output={"status": current_status},
            )
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
        except ValidationError as error:
            raise ChangeIssueStatusError(
                f"Received an unexpected transitions response for issue "
                f"'{action_input.issue_key}'"
            ) from error

        transition = self._find_transition_for_status(
            transitions, action_input.status, action_input.issue_key
        )

        try:
            await self.client.transition_issue(action_input.issue_key, transition.id)
        except httpx.HTTPStatusError as error:
            raise ChangeIssueStatusError.from_response(
                error.response,
                f"Could not change status of issue '{action_input.issue_key}'",
            )

        resolved_status = transition.to.name
        logger.info(
            "Changed Jira issue status",
            issue_key=action_input.issue_key,
            status=resolved_status,
            transition_id=transition.id,
        )

        await self._complete_issue_action(
            run,
            issue_key=action_input.issue_key,
            message=(
                f"Changed issue {action_input.issue_key} to status "
                f"'{resolved_status}'"
            ),
            status_label="Status changed",
            output={"status": resolved_status},
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
    def _find_transition_for_status(
        cls,
        transitions_response: JiraIssueTransitionsResponse,
        target_status: str,
        issue_key: str,
    ) -> JiraIssueTransition:
        normalized_target = cls._normalize_status_name(target_status)
        for transition in transitions_response.transitions:
            if cls._normalize_status_name(transition.to.name) == normalized_target:
                return transition

        available_statuses = cls._get_available_transition_statuses(
            transitions_response
        )
        available_statuses_text = (
            ", ".join(available_statuses) if available_statuses else "none"
        )
        raise ChangeIssueStatusError(
            f"No transition found to status '{target_status}' for issue "
            f"'{issue_key}'. Available target statuses: "
            f"{available_statuses_text}"
        )

    @staticmethod
    def _get_available_transition_statuses(
        transitions_response: JiraIssueTransitionsResponse,
    ) -> list[str]:
        statuses: list[str] = []
        seen: set[str] = set()
        for transition in transitions_response.transitions:
            to_status_name = transition.to.name
            if to_status_name not in seen:
                seen.add(to_status_name)
                statuses.append(to_status_name)
        return statuses
