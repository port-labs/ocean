from aws.core.exporters.eks.nodegroup.models import SingleEksNodegroupRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "eks.amazonaws.com"


NODEGROUP_ARN_RESOURCE_PREFIX = ":nodegroup/"


def _split_identifier(identifier: str) -> tuple[str, str, str | None]:
    """Split "<clusterName>/<nodegroupName>[/<nodegroupUuid>]".

    The UUID is only known when CloudTrail returns the nodegroup ARN (DeleteNodegroup).
    """
    cluster_name, nodegroup_name, *rest = identifier.split("/", 2)
    return cluster_name, nodegroup_name, rest[0] if rest else None


def _nodegroup_arn(context: LiveEventContext) -> str:
    cluster_name, nodegroup_name, nodegroup_uuid = _split_identifier(context.identifier)
    partition = RegionHelper.get_partition()
    arn = (
        f"arn:{partition}:eks:{context.region}:{context.account_id}:"
        f"nodegroup/{cluster_name}/{nodegroup_name}"
    )
    return f"{arn}/{nodegroup_uuid}" if nodegroup_uuid else arn


def _extract_nodegroup_identifier(detail: CloudTrailDetail) -> str | None:
    """Extract '<clusterName>/<nodegroupName>' from CloudTrail request parameters."""
    request_parameters = detail.get("requestParameters", {}) or {}
    # The cluster name is the "name" URI parameter in the EKS REST API
    cluster_name = request_parameters.get("name")
    nodegroup_name = request_parameters.get("nodegroupName")
    if not cluster_name or not nodegroup_name:
        return None
    return f"{cluster_name}/{nodegroup_name}"


def _extract_delete_nodegroup_identifier(detail: CloudTrailDetail) -> str | None:
    """Extract '<clusterName>/<nodegroupName>/<uuid>' from the DeleteNodegroup response ARN."""
    response_elements = detail.get("responseElements") or {}
    nodegroup = response_elements.get("nodegroup") or {}
    nodegroup_arn = nodegroup.get("nodegroupArn") or ""
    _, separator, resource_path = nodegroup_arn.partition(NODEGROUP_ARN_RESOURCE_PREFIX)
    if separator and resource_path.count("/") == 2:
        return resource_path
    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleEksNodegroupRequest:
    cluster_name, nodegroup_name, _ = _split_identifier(context.identifier)
    return SingleEksNodegroupRequest(
        cluster_name=cluster_name,
        nodegroup_name=nodegroup_name,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    cluster_name, nodegroup_name, _ = _split_identifier(context.identifier)
    return {
        "NodegroupArn": _nodegroup_arn(context),
        "NodegroupName": nodegroup_name,
        "ClusterName": cluster_name,
    }


EKS_NODEGROUP_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateNodegroup": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_nodegroup_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateNodegroupConfig": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_nodegroup_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateNodegroupVersion": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_nodegroup_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteNodegroup": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_delete_nodegroup_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
