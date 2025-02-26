class Fragments:
    GROUP_FIELDS = """
        fragment GroupFields on Group {
            id
            name
            webUrl
            description
            visibility
            fullPath
        }
    """


class GroupQueries:
    LIST = f"""
        query Groups($cursor: String) {{
            groups(
                ownedOnly: true,
                first: 100,
                after: $cursor
            ) {{
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    ...GroupFields
                }}
            }}
        }}
        {Fragments.GROUP_FIELDS}
    """
