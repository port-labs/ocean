from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.helpers.exceptions import LinearActionError


class CommentMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_comment(self, issue_id: str, body: str) -> dict[str, object]:
        result = await self.graphql.execute_mutation(
            queries.COMMENT_CREATE,
            {"input": {"issueId": issue_id, "body": body}},
            result_key="commentCreate",
        )
        comment = result.get("comment")
        if not isinstance(comment, dict) or not comment.get("id"):
            raise LinearActionError(
                f"Could not add comment to issue '{issue_id}': Linear returned an empty or incomplete response"
            )
        return comment
