from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations.issue import queries
from linear.core.mutations.issue.types import (
    CommentCreateMutationPayload,
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
    MutationComment,
    MutationCommentResult,
    MutationIssue,
    MutationIssueResult,
)


class IssueMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_issue(self, payload: IssueCreateMutationPayload) -> MutationIssue:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="issueCreate",
        )
        return MutationIssueResult.model_validate(result).issue

    async def update_issue(
        self, issue_id: str, payload: IssueUpdateMutationPayload
    ) -> MutationIssue:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_UPDATE,
            {"id": issue_id, "input": payload.model_dump(exclude_none=True)},
            result_key="issueUpdate",
        )
        return MutationIssueResult.model_validate(result).issue

    async def create_comment(
        self, payload: CommentCreateMutationPayload
    ) -> MutationComment:
        result = await self.graphql.execute_mutation(
            queries.COMMENT_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="commentCreate",
        )
        return MutationCommentResult.model_validate(result).comment

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
