class Fragments:
    PROJECT_FIELDS = """
        fragment ProjectFields on Project {
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
            labels {
                nodes {
                    id
                }
            }
        }
    """


class ProjectQueries:
    LIST = f"""
        query Projects($cursor: String) {{
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
