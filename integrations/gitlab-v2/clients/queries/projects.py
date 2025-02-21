class Fragments:
    PROJECT_FIELDS = """
        fragment ProjectFields on Project {
            name
            webUrl
            description
            fullPath
            languages {
                name 
                share
            }
            repository {
                blobs(paths: ["README.md"]) {
                    nodes {
                        rawBlob
                    }
                }
                rootRef
            }
            labels {
                nodes {
                    color
                    title
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
