from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.core.exporters.ecs.utils import (
    build_service_arn,
    get_cluster_arn_from_service_arn,
    parse_service_arn,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "ecs.amazonaws.com"


def _extract_upsert_service_arn(detail: CloudTrailDetail) -> str | None:
    response_elements = detail.get("responseElements", {})
    service = response_elements.get("service", {})
    service_arn = service.get("serviceArn")
    return service_arn if service_arn else None


def _extract_delete_service_arn(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    cluster = request_parameters.get("cluster")
    service = request_parameters.get("service")
    region = detail.get("awsRegion")
    account_id = detail.get("recipientAccountId")
    if not (cluster and service and region and account_id):
        return None

    return build_service_arn(region, account_id, cluster, service)


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleServiceRequest:
    cluster_name, service_name = parse_service_arn(context.identifier)
    return SingleServiceRequest(
        cluster_name=cluster_name,
        service_name=service_name,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    cluster_name, service_name = parse_service_arn(context.identifier)
    return {
        "ServiceArn": context.identifier,
        "ServiceName": service_name,
        "ClusterArn": get_cluster_arn_from_service_arn(context.identifier),
        "ClusterName": cluster_name,
    }


_SERVICE_UPSERT_MAPPING = CloudTrailEventMapping(
    CloudTrailEventAction.UPSERT,
    _extract_upsert_service_arn,
    event_source=CLOUDTRAIL_EVENT_SOURCE,
)

ECS_SERVICE_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateService": _SERVICE_UPSERT_MAPPING,
        "UpdateService": _SERVICE_UPSERT_MAPPING,
        "DeleteService": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_delete_service_arn,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
