import textwrap


def format_query(query: str) -> str:
    # remove outer single/double quotes
    query = query.strip().strip("'").strip('"')
    # dedent and normalize
    query = textwrap.dedent(query).strip()
    return query
