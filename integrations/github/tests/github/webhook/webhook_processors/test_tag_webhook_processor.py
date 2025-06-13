from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.tag_webhook_processor import (
    TagWebhookProcessor,
)
from github.core.options import SingleTagOptions

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
        kind=ObjectKind.TAG,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"tag"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def tag_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> TagWebhookProcessor:
    return TagWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestTagWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,ref,ref_type,result",
        [
            ("create", "refs/tags/v1.0", "tag", True),
            ("delete", "refs/tags/v1.0", "tag", True),
            ("push", "refs/heads/main", "branch", False),
            ("push", "refs/tags/v1.0", None, False),  # missing ref_type
            ("invalid", "refs/tags/v1.0", "tag", False),
        ],
    )
    async def test_should_process_event(
        self,
        tag_webhook_processor: TagWebhookProcessor,
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

        assert await tag_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, tag_webhook_processor: TagWebhookProcessor
    ) -> None:
        kinds = await tag_webhook_processor.get_matching_kinds(
            tag_webhook_processor.event
        )
        assert ObjectKind.TAG in kinds

    @pytest.mark.parametrize(
        "event_type,is_deletion,expected_updated,expected_deleted",
        [
            ("create", False, True, False),
            ("delete", True, False, True),
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        tag_webhook_processor: TagWebhookProcessor,
        resource_config: ResourceConfig,
        event_type: str,
        is_deletion: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        tag_ref = "refs/tags/v1.0"
        tag_data = {
            "ref": tag_ref,
            "object": {
                "sha": "abc123",
                "type": "commit",
                "url": "https://api.github.com/repos/test-org/repo1/git/commits/abc123",
            },
        }

        payload = {
            "ref": tag_ref,
            "ref_type": "tag",
            "repository": {"name": "test-repo"},
        }

        tag_webhook_processor._event_type = event_type

        if is_deletion:
            result = await tag_webhook_processor.handle_event(payload, resource_config)
        else:
            # Mock the TagExporter
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = tag_data

            with patch(
                "github.webhook.webhook_processors.tag_webhook_processor.RestTagExporter",
                return_value=mock_exporter,
            ):
                result = await tag_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct options
            mock_exporter.get_resource.assert_called_once_with(
                SingleTagOptions(repo_name="test-repo", tag_name=tag_ref)
            )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            assert result.updated_raw_results == [tag_data]

        if expected_deleted:
            assert result.deleted_raw_results == [{"name": tag_ref}]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"ref": "refs/tags/v1.0"}, True),
            ({}, False),  # missing ref
        ],
    )
    async def test_validate_payload(
        self,
        tag_webhook_processor: TagWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await tag_webhook_processor._validate_payload(payload)
        assert result is expected
