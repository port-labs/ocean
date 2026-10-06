from typing import Optional

MIN_GRAPHQL_PAGE_SIZE = 1
GRAPHQL_REDUCTION_SIZE = 5


def reduce_graphql_page_size(current_page_size: int) -> Optional[int]:
    """The next smaller GraphQL `first`, or None when already at the floor."""
    if current_page_size <= MIN_GRAPHQL_PAGE_SIZE:
        return None
    return max(current_page_size - GRAPHQL_REDUCTION_SIZE, MIN_GRAPHQL_PAGE_SIZE)
