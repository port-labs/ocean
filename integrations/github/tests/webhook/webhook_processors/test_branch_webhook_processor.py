from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)
from github.core.options import SingleBranchOptions

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.BRANCH,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".__repository + '_' + .name",
                    title=".__repository + ' ' + .name",
                    blueprint='"branch"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def branch_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> BranchWebhookProcessor:
    return BranchWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestBranchWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,ref,ref_type,result",
        [
            ("create", "refs/heads/main", "branch", True),
            ("delete", "refs/heads/main", "branch", True),
            ("push", "refs/heads/main", "branch", True),
            ("push", "refs/tags/v1.0", "tag", False),
            ("create", "refs/heads/main", None, False),  # missing ref_type
            ("invalid", "refs/heads/main", "branch", False),
        ],
    )
    async def test_should_process_event(
        self,
        branch_webhook_processor: BranchWebhookProcessor,
        github_event: str,
        ref: str,
        ref_type: str | None,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        payload = {"ref": ref}
        if ref_type:
            payload["ref_type"] = ref_type

        event = WebhookEvent(
            trace_id="test-trace-id",
            payload=payload,
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await branch_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, branch_webhook_processor: BranchWebhookProcessor
    ) -> None:
        kinds = await branch_webhook_processor.get_matching_kinds(
            branch_webhook_processor.event
        )
        assert ObjectKind.BRANCH in kinds

    @pytest.mark.parametrize(
        "event_type,is_deletion,expected_updated,expected_deleted",
        [
            ("create", False, True, False),
            ("delete", True, False, True),
            ("push", False, True, False),
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        branch_webhook_processor: BranchWebhookProcessor,
        resource_config: ResourceConfig,
        event_type: str,
        is_deletion: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        branch_ref = "refs/heads/main"
        branch_name = "main"
        branch_data = {
            "name": branch_name,
            "commit": {
                "sha": "abc123",
                "url": "https://api.github.com/repos/test-org/repo1/commits/abc123",
            },
            "protected": True,
        }

        payload = {
            "ref": branch_ref,
            "ref_type": "branch",
            "repository": {"name": "test-repo"},
        }

        branch_webhook_processor._event_type = event_type

        if is_deletion:
            result = await branch_webhook_processor.handle_event(
                payload, resource_config
            )
        else:
            # Mock the BranchExporter
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = branch_data

            with patch(
                "github.webhook.webhook_processors.branch_webhook_processor.RestBranchExporter",
                return_value=mock_exporter,
            ):
                result = await branch_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct options
            mock_exporter.get_resource.assert_called_once_with(
                SingleBranchOptions(repo_name="test-repo", branch_name=branch_name)
            )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            assert result.updated_raw_results == [branch_data]

        if expected_deleted:
            assert result.deleted_raw_results == [{"name": branch_name}]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"ref": "refs/heads/main"}, True),
            ({}, False),  # missing ref
        ],
    )
    async def test_validate_payload(
        self,
        branch_webhook_processor: BranchWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await branch_webhook_processor._validate_payload(payload)
        assert result is expected
