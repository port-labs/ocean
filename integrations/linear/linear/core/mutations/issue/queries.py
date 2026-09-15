ISSUE_CREATE = """
mutation IssueCreate($input: IssueCreateInput!) {
    issueCreate(input: $input) {
        success
        issue {
            id
            identifier
            title
            url
        }
    }
}
"""

ISSUE_UPDATE = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
    issueUpdate(id: $id, input: $input) {
        success
        issue {
            id
            identifier
            title
            url
            state {
                id
                name
            }
        }
    }
}
"""

COMMENT_CREATE = """
mutation CommentCreate($input: CommentCreateInput!) {
    commentCreate(input: $input) {
        success
        comment {
            id
            body
            createdAt
        }
    }
}
"""

ISSUE_ARCHIVE = """
mutation IssueArchive($id: String!) {
    issueArchive(id: $id) {
        success
    }
}
"""

ISSUE_DELETE = """
mutation IssueDelete($id: String!) {
    issueDelete(id: $id) {
        success
    }
}
"""
