import base64
import json
from typing import Any, Generator, cast
from unittest.mock import MagicMock

import port_ocean.context.ocean as ocean_context_module
import pytest
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

ASSET_TYPE = "iam.googleapis.com/ServiceAccount"
ASSET_NAME = (
    "//iam.googleapis.com/projects/p/serviceAccounts/sa@p.iam.gserviceaccount.com"
)
ASSET_PROJECT = "projects/p"

RESOURCE_EVENT: dict[str, Any] = {
    "asset": {
        "assetType": ASSET_TYPE,
        "name": ASSET_NAME,
        "ancestors": [ASSET_PROJECT],
        "resource": {"data": {"name": ASSET_NAME}},
    },
    "deleted": False,
}
IAM_POLICY_EVENT: dict[str, Any] = {
    "asset": {
        "assetType": ASSET_TYPE,
        "name": ASSET_NAME,
        "ancestors": [ASSET_PROJECT],
        "iamPolicy": {
            "bindings": [{"role": "roles/viewer", "members": ["user:a@b.c"]}]
        },
    },
    "deleted": False,
}
# A policy cleared of every binding, in both shapes it could arrive in: the field present and
# empty, or absent altogether. Either way priorAsset carries the policy that was just emptied,
# which is what keeps the event classified and the removed grants deletable.
CLEARED_IAM_POLICY_EVENT: dict[str, Any] = {
    "asset": {
        "assetType": ASSET_TYPE,
        "name": ASSET_NAME,
        "ancestors": [ASSET_PROJECT],
        "iamPolicy": {},
    },
    "deleted": False,
}
CLEARED_IAM_POLICY_EVENT_NO_FIELD: dict[str, Any] = {
    "asset": {
        "assetType": ASSET_TYPE,
        "name": ASSET_NAME,
        "ancestors": [ASSET_PROJECT],
    },
    "priorAsset": {
        "iamPolicy": {"bindings": [{"role": "roles/viewer", "members": []}]}
    },
    "deleted": False,
}
DELETED_IAM_POLICY_EVENT: dict[str, Any] = {
    "asset": {
        "assetType": ASSET_TYPE,
        "name": ASSET_NAME,
        "ancestors": [ASSET_PROJECT],
    },
    "priorAsset": {"iamPolicy": {"bindings": []}},
    "deleted": True,
}
# A feed created with --content-type=org-policy on the same topic. Neither processor consumes it.
ORG_POLICY_EVENT: dict[str, Any] = {
    "asset": {
        "assetType": ASSET_TYPE,
        "name": ASSET_NAME,
        "ancestors": [ASSET_PROJECT],
        "orgPolicy": [{"constraint": "constraints/iam.disableServiceAccountCreation"}],
    },
    "deleted": False,
}


def _pubsub_payload(data: str | dict[str, Any]) -> EventPayload:
    raw = data if isinstance(data, str) else json.dumps(data)
    return {"message": {"data": base64.b64encode(raw.encode()).decode()}}


def _event(payload: EventPayload) -> WebhookEvent:
    return WebhookEvent(trace_id="trace-id", headers={}, payload=payload)


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app: MagicMock = MagicMock()
    mock_app.config.integration.config = {
        "search_all_resources_per_minute_quota": 100,
        "encoded_adc_configuration": None,
    }
    initialize_port_ocean_context(mock_app)
    yield
    ocean_context_module._port_ocean = PortOceanContext(None)


@pytest.fixture
def processors(mock_ocean_context: None) -> dict[str, Any]:
    from gcp_core.webhook.webhook_processors.iam_policy_feed_processor import (
        IamPolicyFeedProcessor,
    )
    from gcp_core.webhook.webhook_processors.resource_feed_processor import (
        ResourceFeedProcessor,
    )

    return {"resource": ResourceFeedProcessor, "iamPolicy": IamPolicyFeedProcessor}


class TestRegistration:
    async def test_every_registered_processor_claims_one_distinct_content_type(
        self, mock_ocean_context: None
    ) -> None:
        """Both feeds publish to one path, so two processors claiming the same content type
        would both handle every event of it, and one claiming none would raise on every event.
        """
        from port_ocean.context.ocean import ocean

        from gcp_core.webhook.registry import register_webhook_processors

        register_webhook_processors()
        register = cast(MagicMock, ocean.app.webhook_manager.register_processor)
        registered = [call.args[1] for call in register.call_args_list]

        contents = [processor.feed_content for processor in registered]
        assert len(registered) == 2
        assert len(set(contents)) == len(contents)


class TestAuthenticate:
    async def test_always_returns_true(self, processors: dict[str, Any]) -> None:
        processor = processors["resource"](event=_event({}))
        assert await processor.authenticate({}, {}) is True


class TestShouldProcessEvent:
    """Every feed publishes to the same path, so exactly one processor may claim an event."""

    @pytest.mark.parametrize(
        ("asset_data", "claimed_by"),
        [
            pytest.param(RESOURCE_EVENT, "resource", id="resource_event"),
            pytest.param(IAM_POLICY_EVENT, "iamPolicy", id="iam_policy_event"),
            pytest.param(CLEARED_IAM_POLICY_EVENT, "iamPolicy", id="cleared_policy"),
            pytest.param(
                CLEARED_IAM_POLICY_EVENT_NO_FIELD,
                "iamPolicy",
                id="cleared_policy_field_absent",
            ),
            pytest.param(DELETED_IAM_POLICY_EVENT, "iamPolicy", id="deleted_asset"),
            pytest.param(ORG_POLICY_EVENT, None, id="org_policy_event"),
        ],
    )
    async def test_the_content_type_decides_the_processor(
        self,
        processors: dict[str, Any],
        asset_data: dict[str, Any],
        claimed_by: str | None,
    ) -> None:
        event = _event(_pubsub_payload(asset_data))
        for name, processor_class in processors.items():
            processor = processor_class(event=event)
            assert await processor.should_process_event(event) is (name == claimed_by)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"not": "a pubsub message"}, id="not_a_pubsub_message"),
            pytest.param({"message": {}}, id="no_data_key"),
            pytest.param(
                _pubsub_payload("You have successfully configured real time feed f"),
                id="feed_created_confirmation",
            ),
            pytest.param(_pubsub_payload("}not json{"), id="unparseable"),
            # Valid JSON the model rejects: a feed whose schema drifted, not a feed we skip.
            pytest.param(
                _pubsub_payload({"asset": "a string"}), id="fails_model_validation"
            ),
            pytest.param(
                _pubsub_payload({"asset": {"ancestors": "projects/x"}}),
                id="wrong_field_type",
            ),
        ],
    )
    async def test_no_processor_claims_an_unusable_payload(
        self, processors: dict[str, Any], payload: EventPayload
    ) -> None:
        event = _event(payload)
        for processor_class in processors.values():
            assert (
                await processor_class(event=event).should_process_event(event) is False
            )


class TestValidatePayload:
    @pytest.mark.parametrize(
        ("asset", "expected"),
        [
            pytest.param(
                {"name": ASSET_NAME, "assetType": ASSET_TYPE, "ancestors": ["p/1"]},
                True,
                id="complete",
            ),
            # An asset with no project ancestor is unsupported, not malformed: handle_event
            # logs it and returns nothing, which is what it did before this check existed.
            pytest.param(
                {"name": ASSET_NAME, "assetType": ASSET_TYPE},
                True,
                id="missing_ancestors",
            ),
            pytest.param(
                {"name": ASSET_NAME, "assetType": ASSET_TYPE, "ancestors": []},
                True,
                id="empty_ancestors",
            ),
            pytest.param(
                {"assetType": ASSET_TYPE, "ancestors": ["p/1"]},
                False,
                id="missing_name",
            ),
            pytest.param(
                {"name": ASSET_NAME, "ancestors": ["p/1"]},
                False,
                id="missing_asset_type",
            ),
        ],
    )
    async def test_the_asset_must_carry_the_identity_handle_event_reads(
        self, processors: dict[str, Any], asset: dict[str, Any], expected: bool
    ) -> None:
        payload = _pubsub_payload({"asset": asset, "deleted": False})
        for processor_class in processors.values():
            processor = processor_class(event=_event(payload))
            assert await processor.validate_payload(payload) is expected

    async def test_a_payload_that_is_not_a_feed_message_is_invalid(
        self, processors: dict[str, Any]
    ) -> None:
        payload: EventPayload = {"not": "a pubsub message"}
        for processor_class in processors.values():
            processor = processor_class(event=_event(payload))
            assert await processor.validate_payload(payload) is False
