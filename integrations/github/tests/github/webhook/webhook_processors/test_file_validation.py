from typing import Any
from github.core.exporters.file_exporter.utils import FileObject
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)

from integration import (
    GithubFilePattern,
    GithubFileResourceConfig,
    GithubFileSelector,
    RepositoryBranchMapping,
    GithubPortAppConfig,
)
from github.webhook.webhook_processors.pull_request_webhook_processor.file_validation import (
    ResourceConfigToPatternMapping,
    FileValidationService,
    get_file_validation_mappings,
)


class MockAsyncGenerator:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def __aiter__(self) -> "MockAsyncGenerator":
        self._iter = iter(self._values)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def file_resource_config() -> GithubFileResourceConfig:
    return GithubFileResourceConfig(
        kind="file",
        selector=GithubFileSelector(
            query="true",
            files=[
                GithubFilePattern(
                    path="*.yaml",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    validationCheck=True,
                ),
                GithubFilePattern(
                    path="*.json",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    validationCheck=False,
                ),
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".metadata.path",
                    title=".metadata.name",
                    blueprint='"githubFile"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_port_app_config(
    file_resource_config: GithubFileResourceConfig,
) -> GithubPortAppConfig:
    return GithubPortAppConfig(
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        repository_type="all",
        resources=[file_resource_config],
    )


@pytest.fixture
def mock_payload() -> dict[str, Any]:
    return {
        "action": "opened",
        "repository": {"name": "test-repo"},
        "pull_request": {
            "number": 101,
            "base": {"sha": "base-sha-123"},
            "head": {"sha": "head-sha-456"},
        },
    }


@pytest.mark.asyncio
class TestFileValidation:
    async def test_get_file_validation_mappings_no_validation_mappings(
        self,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        """Test get_file_validation_mappings when no validation mappings are found."""
        # Test with a repository that doesn't match any patterns
        mappings = get_file_validation_mappings(
            mock_port_app_config, "non-existent-repo"
        )
        assert mappings == []

    async def test_get_file_validation_mappings_with_validation_mappings(
        self,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        """Test get_file_validation_mappings when validation mappings exist."""
        mappings = get_file_validation_mappings(mock_port_app_config, "test-repo")
        assert len(mappings) == 1
        assert isinstance(mappings[0], ResourceConfigToPatternMapping)
        assert len(mappings[0].patterns) == 1
        assert mappings[0].patterns[0].path == "*.yaml"

    async def test_file_validation_service_validate_pull_request_files(
        self,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test FileValidationService.validate_pull_request_files method."""
        mock_pr_exporter = AsyncMock()
        validation_service = FileValidationService(mock_pr_exporter)

        file_object = FileObject(
            content="",
            path="config.yaml",
            repository={"name": "test-repo"},
            metadata={"name": "config.yaml", "path": "config.yaml"},
            branch="main",
            name="config.yaml",
        )

        with patch.object(
            validation_service, "_validate_entity_against_port"
        ) as mock_validate:
            mock_validate.return_value = {
                "success": True,
                "errors": [],
                "response": None,
            }

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

            mock_pr_exporter.create_validation_check.assert_called_once_with(
                repo_name="test-repo", head_sha="head-sha-456"
            )
            mock_pr_exporter.update_check_run.assert_called_once()

    async def test_file_validation_service_validate_pull_request_files_with_errors(
        self,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test FileValidationService.validate_pull_request_files method with validation errors."""
        mock_pr_exporter = AsyncMock()
        validation_service = FileValidationService(mock_pr_exporter)

        file_object = FileObject(
            content="",
            path="config.yaml",
            repository={"name": "test-repo"},
            metadata={"name": "config.yaml", "path": "config.yaml"},
            branch="main",
            name="config.yaml",
        )

        with patch.object(
            validation_service, "_validate_entity_against_port"
        ) as mock_validate:
            mock_validate.return_value = {
                "success": False,
                "errors": ["Validation error"],
                "response": None,
            }

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

            mock_pr_exporter.create_validation_check.assert_called_once_with(
                repo_name="test-repo", head_sha="head-sha-456"
            )
            mock_pr_exporter.update_check_run.assert_called_once()

    async def test_file_validation_service_validate_pull_request_files_exception(
        self,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test FileValidationService.validate_pull_request_files method handles exceptions."""
        mock_pr_exporter = AsyncMock()
        mock_pr_exporter.create_validation_check.side_effect = Exception("API Error")
        validation_service = FileValidationService(mock_pr_exporter)

        file_object = FileObject(
            content="",
            path="config.yaml",
            repository={"name": "test-repo"},
            metadata={"name": "config.yaml", "path": "config.yaml"},
            branch="main",
            name="config.yaml",
        )

        await validation_service.validate_pull_request_files(
            file_object, file_resource_config, "head-sha-456", 101
        )

        # When create_validation_check fails, the method returns early and doesn't call update_check_run
        mock_pr_exporter.update_check_run.assert_not_called()
