class Fragments:
    PROJECT_FIELDS = """
        fragment ProjectFields on Project {
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
            labels {
                nodes {
                    id
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
        query Projects($cursor: String, $filePaths: [String!]!) {{
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
