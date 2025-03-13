class Fragments:
    PROJECT_FIELDS = """
        fragment ProjectFields on Project {
            id
            name
            webUrl
            description
            fullPath
           repository {
                rootRef
                blobs(paths: $filePaths) {
                    nodes {
                        path
                        rawBlob
                    }
                }
            }
            group{
                id
                fullPath            
            }
            labels(first: 100, after: $labelsCursor) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    id
                    title
                }
            }
            languages {
                name 
                share
            }
        }
    """


class ProjectQueries:
    LIST = f"""
        query Projects($cursor: String, $filePaths: [String!]!, $labelsCursor: String) {{
            projects(
                membership: true,
                first: 100,
                after: $cursor
            ) {{
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    ...ProjectFields
                }}
            }}
        }}
        {Fragments.PROJECT_FIELDS}
    """
