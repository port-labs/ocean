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
            group {
                id
                fullPath            
            }
            labels(first: 100) @include(if: $includeLabels) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
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
    LABEL_FIELDS = """
        fragment LabelFields on Label {
            id
            title
        }
    """

class ProjectQueries:
    LIST = f"""
        query Projects($cursor: String, $includeLabels: Boolean!) {{
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

    GET_LABELS = f"""
        query ProjectLabels($fullPath: ID!, $labelsCursor: String) {{
            project(fullPath: $fullPath) {{
                id
                labels(first: 100, after: $labelsCursor) {{
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                    nodes {{
                        ...LabelFields
                    }}
                }}
            }}
        }}
        {Fragments.LABEL_FIELDS}
    """