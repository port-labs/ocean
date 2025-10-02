from typing import Generator, TypeVar
from .models import ResourceGroupTagFilters

T = TypeVar("T")


def turn_sequence_to_chunks(
    sequence: list[T], chunk_size: int
) -> Generator[list[T], None, None]:
    if chunk_size >= len(sequence):
        yield sequence
        return

    start, end = 0, chunk_size

    while start <= len(sequence) and sequence[start:end]:
        yield sequence[start:end]
        start += chunk_size
        end += chunk_size

    return


def build_rg_tag_filter_clause(filters: ResourceGroupTagFilters) -> str:
    """Build KQL where clause for resource group tag filtering with include/exclude logic."""
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
                f"tostring(rgTags['{escaped_key}']) =~ '{escaped_value}'"
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
                f"tostring(rgTags['{escaped_key}']) =~ '{escaped_value}'"
            )

        if exclude_conditions:
            exclude_clause = " or ".join(exclude_conditions)
            conditions.append(f"not ({exclude_clause})")

    if not conditions:
        return ""

    # Combine include and exclude with AND logic
    combined_condition = " and ".join(conditions)
    return f"| where {combined_condition}"
