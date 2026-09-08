import httpx

from github.actions.utils import build_external_id, extract_error_message


class TestBuildExternalId:
    def test_combines_owner_repo_and_run_ids(self) -> None:
        workflow_run = {
            "id": 12345,
            "repository": {"id": 99, "owner": {"id": 1}},
        }

        assert build_external_id(workflow_run) == "gh_1_99_12345"


class TestExtractErrorMessage:
    def test_uses_github_message_field(self) -> None:
        response = httpx.Response(422, json={"message": "Workflow not found"})

        assert extract_error_message(response) == "Workflow not found"

    def test_falls_back_to_raw_text_for_non_json_body(self) -> None:
        response = httpx.Response(502, text="<html>Bad gateway</html>")

        assert extract_error_message(response) == "<html>Bad gateway</html>"

    def test_falls_back_to_raw_text_for_non_object_json(self) -> None:
        response = httpx.Response(500, json=["boom"])

        assert extract_error_message(response) == '["boom"]'

    def test_serializes_non_string_message(self) -> None:
        response = httpx.Response(422, json={"message": {"detail": "nested"}})

        assert extract_error_message(response) == '{"detail": "nested"}'

    def test_falls_back_to_status_code_for_empty_body(self) -> None:
        response = httpx.Response(503, text="   ")

        assert extract_error_message(response) == "HTTP 503"
