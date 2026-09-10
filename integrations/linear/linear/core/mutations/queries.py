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

REACTION_CREATE = """
mutation ReactionCreate($input: ReactionCreateInput!) {
    reactionCreate(input: $input) {
        success
        reaction {
            id
            emoji
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
