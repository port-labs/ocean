from unittest.mock import MagicMock

from gitlab.helpers.exceptions import GitlabTriggerPipelineError


class TestGitlabTriggerPipelineError:
    def test_from_response_string_message(self) -> None:
        response = MagicMock()
        response.json.return_value = {"message": "403 Forbidden"}
        response.text = ""
        response.status_code = 403

        error = GitlabTriggerPipelineError.from_response(
            response, "Could not trigger pipeline"
        )

        assert str(error) == "Could not trigger pipeline: 403 Forbidden"

    def test_from_response_prefers_error_description(self) -> None:
        response = MagicMock()
        response.json.return_value = {
            "error": "insufficient_granular_scope",
            "error_description": "Access denied: missing User: Read",
        }
        response.text = ""
        response.status_code = 403

        error = GitlabTriggerPipelineError.from_response(response, "Failed")

        assert str(error) == "Failed: Access denied: missing User: Read"

    def test_from_response_serializes_structured_message(self) -> None:
        response = MagicMock()
        response.json.return_value = {"message": {"ref": ["is missing"]}}
        response.text = ""
        response.status_code = 400

        error = GitlabTriggerPipelineError.from_response(response, "Failed")

        assert str(error) == 'Failed: {"ref": ["is missing"]}'
