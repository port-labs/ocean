from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from utils import init_terraform_client, should_fetch_health_assessment


@pytest.fixture(autouse=True)
def reset_client_cache() -> Generator[None, None, None]:
    init_terraform_client.cache_clear()
    yield
    init_terraform_client.cache_clear()


class TestInitTerraformClient:
    @patch("utils.ocean")
    @patch("utils.TerraformClient")
    def test_init_terraform_client_success(
        self, mock_terraform_client_class: Any, mock_ocean: Any
    ) -> None:
        mock_config = {
            "terraform_cloud_host": "https://app.terraform.io",
            "terraform_cloud_token": "test-token-123",
        }
        mock_ocean.integration_config = mock_config

        init_terraform_client()

        mock_terraform_client_class.assert_called_once_with(
            "https://app.terraform.io", "test-token-123"
        )

    @patch("utils.ocean")
    @patch("utils.TerraformClient")
    def test_init_terraform_client_returns_instance(
        self, mock_terraform_client_class: Any, mock_ocean: Any
    ) -> None:
        mock_config = {
            "terraform_cloud_host": "https://custom.terraform.io",
            "terraform_cloud_token": "custom-token",
        }
        mock_ocean.integration_config = mock_config
        mock_instance = MagicMock()
        mock_terraform_client_class.return_value = mock_instance

        result = init_terraform_client()

        assert result == mock_instance

    @patch("utils.ocean")
    @patch("utils.TerraformClient")
    def test_init_terraform_client_is_cached(
        self, mock_terraform_client_class: Any, mock_ocean: Any
    ) -> None:
        mock_ocean.integration_config = {
            "terraform_cloud_host": "https://app.terraform.io",
            "terraform_cloud_token": "test-token",
        }

        first = init_terraform_client()
        second = init_terraform_client()

        assert first is second
        assert mock_terraform_client_class.call_count == 1


def _workspace(
    assessments_enabled: bool, relationships: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": "ws-123",
        "attributes": {"assessments-enabled": assessments_enabled},
        "relationships": relationships,
    }


class TestShouldFetchHealthAssessment:
    def test_skips_workspace_with_assessments_disabled(self) -> None:
        workspace = _workspace(False, {"current-assessment-result": {"data": None}})

        assert should_fetch_health_assessment(workspace) is False

    def test_skips_workspace_that_has_never_been_assessed(self) -> None:
        workspace = _workspace(True, {"current-assessment-result": {"data": None}})

        assert should_fetch_health_assessment(workspace) is False

    def test_fetches_workspace_with_an_assessment_result(self) -> None:
        workspace = _workspace(
            True,
            {
                "current-assessment-result": {
                    "data": {"id": "asmtres-1", "type": "assessment-results"}
                }
            },
        )

        assert should_fetch_health_assessment(workspace) is True

    def test_fetches_when_the_relationship_is_absent(self) -> None:
        workspace = _workspace(True, {"organization": {"data": {"id": "org-1"}}})

        assert should_fetch_health_assessment(workspace) is True
