from aws.core.exporters.dynamodb.table.models import SingleTableRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper


def _table_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:dynamodb:{context.region}:{context.account_id}:"
        f"table/{context.identifier}"
    )


def _extract_table_name(detail: CloudTrailDetail) -> str | None:
    table_name = detail.get("requestParameters", {}).get("tableName")
    return table_name if isinstance(table_name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleTableRequest:
    return SingleTableRequest(
        table_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "TableArn": _table_arn(context),
        "TableName": context.identifier,
    }


DYNAMODB_TABLE_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateTable": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT, _extract_table_name
        ),
        "UpdateTable": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT, _extract_table_name
        ),
        "DeleteTable": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE, _extract_table_name
        ),
    },
)
