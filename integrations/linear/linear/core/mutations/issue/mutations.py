from pydantic import ValidationError

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations.issue import queries
from linear.core.mutations.issue.types import (
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
    MutationIssue,
    MutationIssueResult,
)
from linear.helpers.exceptions import CreateIssueError, UpdateIssueError


class IssueMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_issue(
        self, payload: IssueCreateMutationPayload
    ) -> MutationIssue:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="issueCreate",
        )
        try:
            return MutationIssueResult.model_validate(result).issue
        except ValidationError as validation_error:
            raise CreateIssueError(
                "Linear returned an empty or incomplete issue create response"
            ) from validation_error

    async def update_issue(
        self, issue_id: str, payload: IssueUpdateMutationPayload
    ) -> MutationIssue:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_UPDATE,
            {"id": issue_id, "input": payload.model_dump(exclude_none=True)},
            result_key="issueUpdate",
        )
        try:
            return MutationIssueResult.model_validate(result).issue
        except ValidationError as validation_error:
            raise UpdateIssueError(
                "Linear returned an empty or incomplete issue update response"
            ) from validation_error
