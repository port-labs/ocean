from linear.core.exceptions import LinearApiError


def test_from_graphql_errors_includes_validation_field_details() -> None:
    error = LinearApiError.from_graphql_errors(
        [
            {
                "message": "Argument Validation Error",
                "path": ["documentCreate", "input", "issueId"],
                "extensions": {
                    "exception": {
                        "validationErrors": [
                            {
                                "property": "issueId",
                                "constraints": {"isUuid": "issueId must be a UUID"},
                            }
                        ]
                    },
                },
            }
        ]
    )

    assert str(error) == "issueId: issueId must be a UUID"


def test_from_graphql_errors_prefers_user_presentable_message() -> None:
    error = LinearApiError.from_graphql_errors(
        [
            {
                "message": "Invalid input",
                "extensions": {"userPresentableMessage": "Issue not found"},
            }
        ]
    )

    assert str(error) == "Issue not found"


def test_from_graphql_errors_falls_back_to_message_and_field() -> None:
    error = LinearApiError.from_graphql_errors(
        [
            {
                "message": "Argument Validation Error",
                "path": ["documentCreate", "input", "issueId"],
            }
        ]
    )

    assert str(error) == "Argument Validation Error (issueId)"
