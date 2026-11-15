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


def _nodegroup_arn(context: LiveEventContext) -> str:
    # context.identifier is "<clusterName>/<nodegroupName>"
    cluster_name, nodegroup_name = context.identifier.split("/", 1)
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:eks:{context.region}:{context.account_id}:"
        f"nodegroup/{cluster_name}/{nodegroup_name}"
    )


def _extract_nodegroup_identifier(detail: CloudTrailDetail) -> str | None:
    """Extract '<clusterName>/<nodegroupName>' from CloudTrail request parameters."""
    request_parameters = detail.get("requestParameters", {}) or {}
    cluster_name = request_parameters.get("clusterName") or request_parameters.get(
        "name"
    )
    nodegroup_name = request_parameters.get("nodegroupName")
    if not cluster_name or not nodegroup_name:
        return None
    return f"{cluster_name}/{nodegroup_name}"


def _extract_create_nodegroup_identifier(detail: CloudTrailDetail) -> str | None:
    """Extract identifier from CreateNodegroup response elements."""
    response_elements = detail.get("responseElements") or {}
    nodegroup = response_elements.get("nodegroup") or {}
    cluster_name = nodegroup.get("clusterName")
    nodegroup_name = nodegroup.get("nodegroupName")
    if cluster_name and nodegroup_name:
        return f"{cluster_name}/{nodegroup_name}"
    # Fall back to request parameters
    return _extract_nodegroup_identifier(detail)


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleEksNodegroupRequest:
    cluster_name, nodegroup_name = context.identifier.split("/", 1)
    return SingleEksNodegroupRequest(
        cluster_name=cluster_name,
        nodegroup_name=nodegroup_name,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    cluster_name, nodegroup_name = context.identifier.split("/", 1)
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
            _extract_create_nodegroup_identifier,
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
            _extract_nodegroup_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
