from typing import Any

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.helpers.exceptions import (
    CreateIssueError,
    LinearActionError,
    UpdateIssueError,
)


class IssueMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_issue(self, issue_input: dict[str, Any]) -> dict[str, Any]:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_CREATE,
            {"input": issue_input},
            result_key="issueCreate",
        )
        issue = result.get("issue")
        if not isinstance(issue, dict) or not all(
            issue.get(key) for key in ("id", "identifier", "url")
        ):
            raise CreateIssueError(
                "Linear returned an empty or incomplete issue create response"
            )
        return issue

    async def update_issue(
        self, issue_id: str, issue_input: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_UPDATE,
            {"id": issue_id, "input": issue_input},
            result_key="issueUpdate",
        )
        issue = result.get("issue")
        if not isinstance(issue, dict) or not all(
            issue.get(key) for key in ("id", "identifier", "url")
        ):
            raise UpdateIssueError(
                "Linear returned an empty or incomplete issue update response"
            )
        return issue

    async def resolve_state_id(self, issue_id: str, state_name: str) -> str:
        data = await self.graphql.execute(
            queries.RESOLVE_STATE_BY_NAME,
            {"issueId": issue_id, "stateName": state_name},
        )
        issue = data.get("issue")
        if not isinstance(issue, dict):
            raise LinearActionError(
                f"Could not resolve state '{state_name}' for issue '{issue_id}'"
            )
        team = issue.get("team")
        if not isinstance(team, dict):
            raise LinearActionError(
                f"Could not resolve state '{state_name}' for issue '{issue_id}'"
            )
        states = team.get("states", {}).get("nodes", [])
        if not states or not isinstance(states[0], dict) or not states[0].get("id"):
            raise LinearActionError(
                f"Could not find workflow state '{state_name}' for issue '{issue_id}'"
            )
        return str(states[0]["id"])

    async def archive_issue(self, issue_id: str) -> None:
        await self.graphql.execute_mutation(
            queries.ISSUE_ARCHIVE,
            {"id": issue_id},
            result_key="issueArchive",
        )

    async def delete_issue(self, issue_id: str) -> None:
        await self.graphql.execute_mutation(
            queries.ISSUE_DELETE,
            {"id": issue_id},
            result_key="issueDelete",
        )
