import httpx
import pytest

from jira.actions.exceptions import JiraActionError


def _make_response(
    *,
    status_code: int = 400,
    json_body: object | None = None,
    text: str | None = None,
) -> httpx.Response:
    kwargs: dict[str, object] = {
        "status_code": status_code,
        "request": httpx.Request("GET", "https://example.atlassian.net"),
    }
    if json_body is not None:
        kwargs["json"] = json_body
    elif text is not None:
        kwargs["text"] = text
    return httpx.Response(**kwargs)  # type: ignore[arg-type]


def test_from_response_uses_error_messages() -> None:
    # Arrange
    response = _make_response(
        json_body={"errorMessages": ["First error", "Second error"]}
    )

    # Act
    error = JiraActionError.from_response(response, "Could not create issue")

    # Assert
    assert str(error) == ("Could not create issue: First error; Second error")


def test_from_response_uses_errors_dict() -> None:
    # Arrange
    response = _make_response(
        json_body={"errors": {"summary": "Field is required", "project": "Invalid key"}}
    )

    # Act
    error = JiraActionError.from_response(response, "Validation failed")

    # Assert
    assert str(error) == (
        "Validation failed: summary: Field is required; project: Invalid key"
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_detail"),
    [
        ("message", "Transition is unavailable", "Transition is unavailable"),
        ("error", "Unauthorized", "Unauthorized"),
    ],
)
def test_from_response_uses_message_or_error_field(
    field_name: str, field_value: str, expected_detail: str
) -> None:
    # Arrange
    response = _make_response(json_body={field_name: field_value})

    # Act
    error = JiraActionError.from_response(response, "Request failed")

    # Assert
    assert str(error) == f"Request failed: {expected_detail}"


def test_from_response_serializes_non_string_message_field() -> None:
    # Arrange
    response = _make_response(json_body={"message": {"code": "INVALID"}})

    # Act
    error = JiraActionError.from_response(response, "Request failed")

    # Assert
    assert str(error) == 'Request failed: {"code": "INVALID"}'


def test_from_response_prefers_error_messages_over_errors_dict() -> None:
    # Arrange
    response = _make_response(
        json_body={
            "errorMessages": ["Primary message"],
            "errors": {"summary": "Should not be used"},
        }
    )

    # Act
    error = JiraActionError.from_response(response, "Request failed")

    # Assert
    assert str(error) == "Request failed: Primary message"


def test_from_response_falls_back_to_response_text_for_invalid_json() -> None:
    # Arrange
    response = _make_response(text="Plain text error body")

    # Act
    error = JiraActionError.from_response(response, "Request failed")

    # Assert
    assert str(error) == "Request failed: Plain text error body"


def test_from_response_falls_back_to_status_code_for_empty_body() -> None:
    # Arrange
    response = _make_response(status_code=503)

    # Act
    error = JiraActionError.from_response(response, "Request failed")

    # Assert
    assert str(error) == "Request failed: HTTP 503"


def test_from_response_falls_back_to_response_text_for_non_object_json() -> None:
    # Arrange
    response = _make_response(json_body=["not", "a", "dict"])

    # Act
    error = JiraActionError.from_response(response, "Request failed")

    # Assert
    assert str(error) == 'Request failed: ["not","a","dict"]'
