from aws.core.exporters.ecr.repository.models import SingleRepositoryRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper


def _repository_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:ecr:{context.region}:{context.account_id}:"
        f"repository/{context.identifier}"
    )


def _extract_repository_name(detail: CloudTrailDetail) -> str | None:
    repository_name = detail.get("requestParameters", {}).get("repositoryName")
    return repository_name if isinstance(repository_name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleRepositoryRequest:
    return SingleRepositoryRequest(
        repository_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "RepositoryArn": _repository_arn(context),
        "RepositoryName": context.identifier,
    }


ECR_REPOSITORY_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateRepository": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_repository_name,
            event_source="ecr.amazonaws.com",
        ),
        "DeleteRepository": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_repository_name,
            event_source="ecr.amazonaws.com",
        ),
    },
)
