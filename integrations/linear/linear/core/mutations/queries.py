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

RESOLVE_STATE_BY_NAME = """
query ResolveStateByName($issueId: String!, $stateName: String!) {
    issue(id: $issueId) {
        team {
            states(filter: { name: { eq: $stateName } }, first: 1) {
                nodes {
                    id
                    name
                }
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

DOCUMENT_CREATE = """
mutation DocumentCreate($input: DocumentCreateInput!) {
    documentCreate(input: $input) {
        success
        document {
            id
            title
            url
        }
    }
}
"""
