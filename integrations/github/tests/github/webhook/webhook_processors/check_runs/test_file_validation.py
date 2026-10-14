from typing import Any
from github.core.exporters.file_exporter.utils import FileObject
import httpx
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.core.models import Entity

from github.helpers.utils import ObjectKind
from integration import (
    GithubFilePattern,
    GithubFileResourceConfig,
    GithubFileSelector,
    RepositoryBranchMapping,
    GithubPortAppConfig,
)
from github.webhook.webhook_processors.check_runs.file_validation import (
    ResourceConfigToPatternMapping,
    FileValidationService,
    _format_port_http_error,
    get_file_validation_mappings,
)

JQ_SEARCH_PATH = (
    "github.webhook.webhook_processors.check_runs.file_validation."
    "JQEntityProcessor._search_as_object"
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
        kind=ObjectKind.FILE,
        selector=GithubFileSelector(
            query="true",
            files=[
                GithubFilePattern(
                    organization="test-org",
                    path="*.yaml",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    validationCheck=True,
                ),
                GithubFilePattern(
                    organization="test-org",
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
        "organization": {"login": "test-org"},
    }


@pytest.fixture
def file_object() -> FileObject:
    return FileObject(
        organization="test-org",
        content="",
        path="config.yaml",
        repository={"name": "test-repo"},
        metadata={"name": "config.yaml", "path": "config.yaml"},
        branch="main",
        name="config.yaml",
        __base_jq=".content",
    )


def _extracted_entity(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "identifier": "svc-1",
        "title": "Service 1",
        "blueprint": "service",
        "properties": {},
        "relations": {},
    }
    values.update(overrides)
    return values


def _http_status_error(
    status_code: int,
    json_body: dict[str, Any] | None = None,
    text: str | None = None,
) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "POST", "https://api.getport.io/v1/blueprints/service/entities"
    )
    if json_body is not None:
        response = httpx.Response(status_code, json=json_body, request=request)
    else:
        response = httpx.Response(status_code, text=text or "", request=request)
    return httpx.HTTPStatusError(
        f"{status_code} error", request=request, response=response
    )


@pytest.mark.asyncio
class TestFileValidation:
    async def test_get_file_validation_mappings_no_file_resources(
        self,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        """Test get_file_validation_mappings when no file resources are configured."""
        # Create a port app config with no validation patterns
        port_app_config_no_validation = GithubPortAppConfig(
            delete_dependent_entities=True,
            create_missing_related_entities=False,
            repository_type="all",
            resources=[],
        )

        mappings = get_file_validation_mappings(port_app_config_no_validation)
        assert mappings == []

    async def test_get_file_validation_mappings_with_validation_mappings(
        self,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        """Test get_file_validation_mappings when validation mappings exist."""
        mappings = get_file_validation_mappings(mock_port_app_config)
        assert len(mappings) == 1
        assert isinstance(mappings[0], ResourceConfigToPatternMapping)
        assert len(mappings[0].patterns) == 1
        assert mappings[0].patterns[0].path == "*.yaml"

    async def test_file_validation_service_validate_pull_request_files(
        self,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test FileValidationService.validate_pull_request_files method."""
        validation_service = FileValidationService("test-org")

        file_object = FileObject(
            organization="test-org",
            content="",
            path="config.yaml",
            repository={"name": "test-repo"},
            metadata={"name": "config.yaml", "path": "config.yaml"},
            branch="main",
            name="config.yaml",
            __base_jq=".content",
        )

        with (
            patch.object(
                validation_service.check_runs, "create_validation_check"
            ) as mock_create_check,
            patch.object(
                validation_service.check_runs, "update_check_run"
            ) as mock_update_check,
            patch.object(
                validation_service, "_validate_entity_against_port"
            ) as mock_validate,
        ):
            mock_create_check.return_value = "check-run-id-123"
            mock_validate.return_value = {
                "success": True,
                "errors": [],
                "response": None,
            }

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

            mock_create_check.assert_called_once_with(
                organization="test-org", repo_name="test-repo", head_sha="head-sha-456"
            )
            mock_update_check.assert_called_once()

    async def test_file_validation_service_validate_pull_request_files_with_errors(
        self,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test FileValidationService.validate_pull_request_files method with validation errors."""
        validation_service = FileValidationService("test-org")

        file_object = FileObject(
            organization="test-org",
            content="",
            path="config.yaml",
            repository={"name": "test-repo"},
            metadata={"name": "config.yaml", "path": "config.yaml"},
            branch="main",
            name="config.yaml",
            __base_jq=".content",
        )

        with (
            patch.object(
                validation_service.check_runs, "create_validation_check"
            ) as mock_create_check,
            patch.object(
                validation_service.check_runs, "update_check_run"
            ) as mock_update_check,
            patch.object(
                validation_service, "_validate_entity_against_port"
            ) as mock_validate,
        ):
            mock_create_check.return_value = "check-run-id-123"
            mock_validate.return_value = {
                "success": False,
                "errors": ["Validation error"],
                "response": None,
            }

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

            mock_create_check.assert_called_once_with(
                organization="test-org", repo_name="test-repo", head_sha="head-sha-456"
            )
            mock_update_check.assert_called_once()
            assert mock_update_check.call_args.args[4] == "failure"
            assert "Validation error" in mock_update_check.call_args.args[7]

    async def test_file_validation_service_validate_pull_request_files_exception(
        self,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test FileValidationService.validate_pull_request_files method handles exceptions."""
        validation_service = FileValidationService("test-org")

        file_object = FileObject(
            organization="test-org",
            content="",
            path="config.yaml",
            repository={"name": "test-repo"},
            metadata={"name": "config.yaml", "path": "config.yaml"},
            branch="main",
            name="config.yaml",
            __base_jq=".content",
        )

        with (
            patch.object(
                validation_service.check_runs, "create_validation_check"
            ) as mock_create_check,
            patch.object(
                validation_service.check_runs, "update_check_run"
            ) as mock_update_check,
        ):
            mock_create_check.side_effect = Exception("API Error")

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

            # When create_validation_check fails, the method returns early and doesn't call update_check_run
            mock_update_check.assert_not_called()

    async def test_validate_entity_against_port_success(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")
        entity = Entity(
            identifier="svc-1",
            blueprint="service",
            title="Service 1",
            properties={},
            relations={},
        )

        with (
            patch(JQ_SEARCH_PATH, new_callable=AsyncMock) as mock_jq,
            patch.object(
                ocean.port_client, "upsert_entity", new_callable=AsyncMock
            ) as mock_upsert,
        ):
            mock_jq.return_value = _extracted_entity()
            mock_upsert.return_value = entity

            result = await validation_service._validate_entity_against_port(
                file_object, file_resource_config
            )

        assert result["success"] is True
        assert result["errors"] == []
        assert result["response"] is entity
        assert mock_upsert.call_args.kwargs["should_raise"] is True

    async def test_validate_entity_against_port_false_on_unmet_dependency(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")

        with (
            patch(JQ_SEARCH_PATH, new_callable=AsyncMock) as mock_jq,
            patch.object(
                ocean.port_client, "upsert_entity", new_callable=AsyncMock
            ) as mock_upsert,
        ):
            mock_jq.return_value = _extracted_entity()
            mock_upsert.return_value = False

            result = await validation_service._validate_entity_against_port(
                file_object, file_resource_config
            )

        assert result["success"] is False
        assert result["errors"]
        assert "related entity or blueprint not found" in result["errors"][0]
        assert mock_upsert.call_args.kwargs["should_raise"] is True

    async def test_validate_entity_against_port_false_on_422(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")
        port_message = "Invalid enum value 'broken' for property 'status'"

        with (
            patch(JQ_SEARCH_PATH, new_callable=AsyncMock) as mock_jq,
            patch.object(
                ocean.port_client, "upsert_entity", new_callable=AsyncMock
            ) as mock_upsert,
        ):
            mock_jq.return_value = _extracted_entity()
            mock_upsert.side_effect = _http_status_error(
                422,
                json_body={
                    "ok": False,
                    "error": "invalid_request",
                    "message": port_message,
                },
            )

            result = await validation_service._validate_entity_against_port(
                file_object, file_resource_config
            )

        assert result["success"] is False
        assert result["errors"] == [port_message]
        assert mock_upsert.call_args.kwargs["should_raise"] is True

    async def test_validate_entity_against_port_jq_failure_does_not_unbound_local(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")

        with patch(
            JQ_SEARCH_PATH,
            new_callable=AsyncMock,
            side_effect=Exception("jq failed"),
        ):
            result = await validation_service._validate_entity_against_port(
                file_object, file_resource_config
            )

        assert result["success"] is False
        assert result["errors"] == ["jq failed"]

    async def test_validate_entity_against_port_invalid_blueprint_type(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")

        with patch(
            JQ_SEARCH_PATH,
            new_callable=AsyncMock,
            return_value=_extracted_entity(blueprint=123),
        ):
            result = await validation_service._validate_entity_against_port(
                file_object, file_resource_config
            )

        assert result["success"] is False
        assert result["errors"] == ["Blueprint is not a string"]

    async def test_validate_pull_request_files_fails_check_on_port_404(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")

        with (
            patch.object(
                validation_service.check_runs, "create_validation_check"
            ) as mock_create_check,
            patch.object(
                validation_service.check_runs, "update_check_run"
            ) as mock_update_check,
            patch(
                JQ_SEARCH_PATH,
                new_callable=AsyncMock,
                return_value=_extracted_entity(),
            ),
            patch.object(
                ocean.port_client, "upsert_entity", new_callable=AsyncMock
            ) as mock_upsert,
        ):
            mock_create_check.return_value = "check-run-id-123"
            mock_upsert.return_value = False

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

        mock_update_check.assert_called_once()
        assert mock_update_check.call_args.args[4] == "failure"
        assert (
            "related entity or blueprint not found"
            in mock_update_check.call_args.args[7]
        )

    async def test_validate_pull_request_files_fails_check_on_port_422(
        self,
        file_resource_config: GithubFileResourceConfig,
        file_object: FileObject,
    ) -> None:
        validation_service = FileValidationService("test-org")
        port_message = "Missing required property 'owner'"

        with (
            patch.object(
                validation_service.check_runs, "create_validation_check"
            ) as mock_create_check,
            patch.object(
                validation_service.check_runs, "update_check_run"
            ) as mock_update_check,
            patch(
                JQ_SEARCH_PATH,
                new_callable=AsyncMock,
                return_value=_extracted_entity(),
            ),
            patch.object(
                ocean.port_client, "upsert_entity", new_callable=AsyncMock
            ) as mock_upsert,
        ):
            mock_create_check.return_value = "check-run-id-123"
            mock_upsert.side_effect = _http_status_error(
                422,
                json_body={
                    "ok": False,
                    "error": "invalid_request",
                    "message": port_message,
                },
            )

            await validation_service.validate_pull_request_files(
                file_object, file_resource_config, "head-sha-456", 101
            )

        mock_update_check.assert_called_once()
        assert mock_update_check.call_args.args[4] == "failure"
        assert port_message in mock_update_check.call_args.args[7]


class TestFormatPortHttpError:
    def test_prefers_port_message_from_json_body(self) -> None:
        error = _http_status_error(
            422,
            json_body={
                "ok": False,
                "error": "invalid_request",
                "message": "bad enum value",
            },
        )
        assert _format_port_http_error(error) == "bad enum value"

    def test_falls_back_to_error_field(self) -> None:
        error = _http_status_error(404, json_body={"ok": False, "error": "not_found"})
        assert _format_port_http_error(error) == "not_found"

    def test_falls_back_to_response_text(self) -> None:
        error = _http_status_error(500, text="internal server error")
        assert _format_port_http_error(error) == "internal server error"
