from plain.exceptions import (
    PlainGraphQLError,
    PlainHTTPError,
    missing_permission_names,
)


def test_graphql_error_uses_error_messages() -> None:
    error = PlainGraphQLError(
        [
            {"message": "Not authorized", "path": ["threads"]},
            {"message": "Missing permission thread:read"},
        ]
    )

    assert isinstance(error, Exception)
    assert str(error) == "Not authorized; Missing permission thread:read"
    assert error.errors[0]["path"] == ["threads"]


def test_graphql_error_falls_back_when_messages_are_missing() -> None:
    error = PlainGraphQLError([{"extensions": {"code": "FORBIDDEN"}}])

    assert str(error) == "Unknown GraphQL error"


def test_missing_permission_names_reads_plain_forbidden_payload() -> None:
    payload = {
        "errors": [
            {
                "message": 'Insufficient permissions, missing "timeline:read".',
                "path": ["thread", "timelineEntries"],
            }
        ],
        "data": {"thread": None},
    }

    assert missing_permission_names(payload) == ["timeline:read"]


def test_http_error_includes_status_and_body() -> None:
    error = PlainHTTPError(401, '{"message":"Unauthorized"}')

    assert error.status_code == 401
    assert error.body == '{"message":"Unauthorized"}'
    assert str(error) == 'Plain API HTTP 401: {"message":"Unauthorized"}'
