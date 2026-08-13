from unittest.mock import MagicMock, patch

from aws.webhook.consts import CLOUDTRAIL_WEBHOOK_PATH
from aws.webhook.registry import register_cloudtrail_live_events
from aws.webhook.webhook_processors.cloudtrail_webhook_processor import (
    CloudTrailWebhookProcessor,
)

MODULE = "aws.webhook.registry"


def test_register_cloudtrail_live_events_when_configured() -> None:
    mock_ocean = MagicMock()

    with (
        patch(f"{MODULE}.ocean", mock_ocean),
        patch(f"{MODULE}.get_live_events_api_key", return_value="secret"),
    ):
        register_cloudtrail_live_events()

    mock_ocean.add_webhook_processor.assert_called_once_with(
        CLOUDTRAIL_WEBHOOK_PATH, CloudTrailWebhookProcessor
    )


def test_skips_registration_when_api_key_missing() -> None:
    mock_ocean = MagicMock()

    with (
        patch(f"{MODULE}.ocean", mock_ocean),
        patch(f"{MODULE}.get_live_events_api_key", return_value=None),
    ):
        register_cloudtrail_live_events()

    mock_ocean.add_webhook_processor.assert_not_called()
