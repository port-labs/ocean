import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)
from github.core.options import ListFolderOptions
from integration import (
    GithubFolderResourceConfig,
    RepositoryBranchMapping,
    FolderSelector,
    GithubFolderSelector,
)

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def folder_resource_config() -> GithubFolderResourceConfig:
    return GithubFolderResourceConfig(
        kind=ObjectKind.FOLDER,
        selector=GithubFolderSelector(
            query="true",
            folders=[
                FolderSelector(
                    path="folder1/*",
                    repos=[
                        RepositoryBranchMapping(name="test-repo", branch="main"),
                        RepositoryBranchMapping(name="another-repo", branch="dev"),
                    ],
                ),
                FolderSelector(
                    path="folder2/*",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                ),
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".path",
                    title=".name",
                    blueprint='"githubFolder"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def folder_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> FolderWebhookProcessor:
    return FolderWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestFolderWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,result",
        [("push", True), ("invalid", False), ("repository", False)],
    )
    async def test_should_process_event(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
        github_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await folder_webhook_processor._should_process_event(event) is result

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"ref": "refs/heads/main", "repository": {"name": "test"}}, True),
            ({"ref": "refs/heads/main"}, False),
            ({"repository": {"name": "test"}}, False),
            ({}, False),
        ],
    )
    async def test_validate_payload(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
        payload: dict,
        expected: bool,
    ) -> None:
        result = await folder_webhook_processor.validate_payload(payload)
        assert result is expected

    async def test_get_matching_kinds(
        self, folder_webhook_processor: FolderWebhookProcessor
    ) -> None:
        kinds = await folder_webhook_processor.get_matching_kinds(
            folder_webhook_processor.event
        )
        assert ObjectKind.FOLDER in kinds

    async def test_handle_push_event(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
        folder_resource_config: GithubFolderResourceConfig,
    ) -> None:
        repo_name = "test-repo"
        branch_name = "main"
        ref_sha = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"

        payload = {
            "repository": {"name": repo_name},
            "ref": f"refs/heads/{branch_name}",
            "after": ref_sha,
        }

        expected_folders_from_exporter = [
            {
                "path": "folder1/subfolder1",
                "name": "subfolder1",
                "repo": repo_name,
                "branch": branch_name,
            },
            {
                "path": "folder1/subfolder2",
                "name": "subfolder2",
                "repo": repo_name,
                "branch": branch_name,
            },
            {
                "path": "folder2/subfolderA",
                "name": "subfolderA",
                "repo": repo_name,
                "branch": branch_name,
            },
        ]

        async def async_generator():
            yield [expected_folders_from_exporter[0], expected_folders_from_exporter[1]]
            yield [expected_folders_from_exporter[2]]

        # Mock the RestFolderExporter and its get_paginated_resources method
        mock_exporter = MagicMock()
        mock_exporter.get_paginated_resources.return_value = async_generator()

        with patch(
            "github.webhook.webhook_processors.folder_webhook_processor.RestFolderExporter",
            return_value=mock_exporter,
        ):
            result = await folder_webhook_processor.handle_event(
                payload, folder_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == expected_folders_from_exporter
        assert result.deleted_raw_results == []

        # Verify exporter was called with correct options for each folder selector
        mock_exporter.get_paginated_resources.assert_any_call(
            ListFolderOptions(
                repo={"name": repo_name}, path="folder1/*", branch=branch_name
            )
        )
        mock_exporter.get_paginated_resources.assert_any_call(
            ListFolderOptions(
                repo={"name": repo_name}, path="folder2/*", branch=branch_name
            )
        )
        assert mock_exporter.get_paginated_resources.call_count == 2
