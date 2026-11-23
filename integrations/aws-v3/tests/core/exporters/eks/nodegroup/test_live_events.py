from unittest.mock import patch

from aws.core.exporters.eks.nodegroup.live_events import EKS_NODEGROUP_LIVE_EVENTS
from aws.core.exporters.eks.nodegroup.models import SingleEksNodegroupRequest
from aws.core.helpers.metadata.types import CloudTrailDetail, LiveEventContext

_ACCOUNT_ID = "123456789012"
_REGION = "us-west-2"
_UUID = "abcdef12-3456-7890-abcd-ef1234567890"
_FULL_ARN = (
    f"arn:aws:eks:{_REGION}:{_ACCOUNT_ID}:nodegroup/my-cluster/my-nodegroup/{_UUID}"
)


def _context(identifier: str) -> LiveEventContext:
    return LiveEventContext(
        identifier=identifier, account_id=_ACCOUNT_ID, region=_REGION
    )


def _extract(event_name: str, detail: CloudTrailDetail) -> str | None:
    mapping = EKS_NODEGROUP_LIVE_EVENTS.cloudtrail_mappings[event_name]
    return mapping.extract_identifier(detail)


def test_delete_identifier_includes_uuid_from_response_arn() -> None:
    detail: CloudTrailDetail = {
        "requestParameters": {"name": "my-cluster", "nodegroupName": "my-nodegroup"},
        "responseElements": {"nodegroup": {"nodegroupArn": _FULL_ARN}},
    }

    assert _extract("DeleteNodegroup", detail) == f"my-cluster/my-nodegroup/{_UUID}"


def test_delete_identifier_returns_none_without_response_arn() -> None:
    detail: CloudTrailDetail = {
        "requestParameters": {"name": "my-cluster", "nodegroupName": "my-nodegroup"},
        "responseElements": {},
    }

    assert _extract("DeleteNodegroup", detail) is None


@patch(
    "aws.core.exporters.eks.nodegroup.live_events.RegionHelper.get_partition",
    return_value="aws",
)
def test_deletion_properties_use_full_arn_when_uuid_known(_: object) -> None:
    properties = EKS_NODEGROUP_LIVE_EVENTS.deletion_identifier_properties_factory(
        _context(f"my-cluster/my-nodegroup/{_UUID}")
    )

    assert properties == {
        "NodegroupArn": _FULL_ARN,
        "NodegroupName": "my-nodegroup",
        "ClusterName": "my-cluster",
    }


@patch(
    "aws.core.exporters.eks.nodegroup.live_events.RegionHelper.get_partition",
    return_value="aws",
)
def test_deletion_properties_without_uuid(_: object) -> None:
    properties = EKS_NODEGROUP_LIVE_EVENTS.deletion_identifier_properties_factory(
        _context("my-cluster/my-nodegroup")
    )

    assert properties["NodegroupArn"] == (
        f"arn:aws:eks:{_REGION}:{_ACCOUNT_ID}:nodegroup/my-cluster/my-nodegroup"
    )
    assert properties["NodegroupName"] == "my-nodegroup"


def test_request_factory_ignores_uuid() -> None:
    request = EKS_NODEGROUP_LIVE_EVENTS.request_factory(
        _context(f"my-cluster/my-nodegroup/{_UUID}"), []
    )

    assert isinstance(request, SingleEksNodegroupRequest)
    assert request.cluster_name == "my-cluster"
    assert request.nodegroup_name == "my-nodegroup"
