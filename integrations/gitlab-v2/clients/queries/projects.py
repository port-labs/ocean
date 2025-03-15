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
        query Projects($cursor: String, $labelsCursor: String) {{
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
