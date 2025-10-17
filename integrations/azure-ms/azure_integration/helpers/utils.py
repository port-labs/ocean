from azure_integration.models import ResourceGroupTagFilters


def build_rg_tag_filter_clause(
    filters: ResourceGroupTagFilters, tag_key_name: str = "tags"
) -> str:
    """
    Constructs a KQL `where` clause for filtering based on resource group tags.

    This function builds a KQL filter clause that can be appended to a query.
    It supports both inclusion and exclusion criteria for tags.

    - Included tags are combined with AND logic (all must be present).
    - Excluded tags are combined with OR logic inside a NOT clause (none should be present).
    - If both included and excluded filters are provided, they are combined with AND.

    Args:
        filters: A ResourceGroupTagFilters object containing `included` and `excluded` tag dictionaries.
        tag_key_name: The name of the tag column/field in the KQL query. Defaults to "tags".

    Returns:
        A string representing the KQL `| where ...` clause, or an empty string if no filters are provided.
    """
    if not filters.has_filters():
        return ""

    conditions: list[str] = []

    # Build include conditions (AND logic within include)
    if filters.included:
        include_conditions = []
        for key, value in filters.included.items():
            escaped_key = key.replace("'", "''")
            escaped_value = value.replace("'", "''")
            include_conditions.append(
                f"tostring({tag_key_name}['{escaped_key}']) =~ '{escaped_value}'"
            )

        if include_conditions:
            include_clause = " and ".join(include_conditions)
            conditions.append(f"({include_clause})")

    # Build exclude conditions (OR logic within exclude, then NOT the whole thing)
    if filters.excluded:
        exclude_conditions = []
        for key, value in filters.excluded.items():
            escaped_key = key.replace("'", "''")
            escaped_value = value.replace("'", "''")
            exclude_conditions.append(
                f"tostring({tag_key_name}['{escaped_key}']) =~ '{escaped_value}'"
            )

        if exclude_conditions:
            exclude_clause = " or ".join(exclude_conditions)
            conditions.append(f"not ({exclude_clause})")

    if not conditions:
        return ""

    # Combine include and exclude with AND logic
    combined_condition = " and ".join(conditions)
    return f"| where {combined_condition}"
