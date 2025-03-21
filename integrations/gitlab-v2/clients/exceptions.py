from typing import Any


class GraphQLQueryError(Exception):
    """Raised when a GraphQL query fails with errors in the response."""

    def __init__(self, message: str, errors: list[dict[str, Any]]):
        super().__init__(message)
        self.errors = errors  # Store the GraphQL errors for debugging
