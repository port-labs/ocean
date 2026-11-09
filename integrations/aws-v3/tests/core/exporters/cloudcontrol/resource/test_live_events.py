from aws.core.exporters.cloudcontrol.resource.live_events import (
    build_cloud_control_live_events,
)
from aws.core.exporters.cloudcontrol.resource.metadata import (
    CloudControlExporterMetadata,
)
from aws.core.exporters.cloudcontrol.resource.models import (
    SingleCloudControlResourceRequest,
)
from aws.core.helpers.metadata.types import LiveEventContext

_CONTEXT = LiveEventContext(
    identifier="my-role",
    account_id="111122223333",
    region="us-east-1",
)


def test_request_factory_builds_get_resource_request() -> None:
    live_events = build_cloud_control_live_events("AWS::IAM::Role")

    request = live_events.request_factory(_CONTEXT, [])

    assert request == SingleCloudControlResourceRequest(
        type_name="AWS::IAM::Role",
        identifier="my-role",
        region="us-east-1",
        account_id="111122223333",
        include=[],
    )


def test_deletion_properties_use_identifier() -> None:
    live_events = build_cloud_control_live_events("AWS::IAM::Role")

    assert live_events.deletion_identifier_properties_factory(_CONTEXT) == {
        "Identifier": "my-role"
    }


def test_metadata_for_type_has_live_events() -> None:
    metadata = CloudControlExporterMetadata.for_type("AWS::IAM::Role")

    assert metadata.live_events is not None
    request = metadata.live_events.request_factory(_CONTEXT, [])
    assert isinstance(request, SingleCloudControlResourceRequest)
    assert request.type_name == "AWS::IAM::Role"
