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
