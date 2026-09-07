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
