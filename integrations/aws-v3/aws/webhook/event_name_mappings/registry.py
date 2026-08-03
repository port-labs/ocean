from aws.webhook.event_name_mappings.lambda_function import MAPPINGS as LAMBDA_MAPPINGS
from aws.webhook.event_name_mappings.mapping import EventNameMapping
from aws.webhook.event_name_mappings.s3_bucket import MAPPINGS as S3_MAPPINGS

_ALL_MAPPINGS: tuple[dict[str, EventNameMapping], ...] = (
    S3_MAPPINGS,
    LAMBDA_MAPPINGS,
)

EVENT_NAME_MAPPINGS: dict[str, EventNameMapping] = {
    event_name: mapping
    for mappings in _ALL_MAPPINGS
    for event_name, mapping in mappings.items()
}
