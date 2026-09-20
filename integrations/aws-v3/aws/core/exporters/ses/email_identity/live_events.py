from aws.core.exporters.ses.email_identity.models import SingleEmailIdentityRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "ses.amazonaws.com"


def _extract_email_identity(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    identity = request_parameters.get("emailIdentity")
    return identity if isinstance(identity, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleEmailIdentityRequest:
    return SingleEmailIdentityRequest(
        identity_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "IdentityName": context.identifier,
    }


_EMAIL_IDENTITY_UPSERT_MAPPING = CloudTrailEventMapping(
    CloudTrailEventAction.UPSERT,
    _extract_email_identity,
    event_source=CLOUDTRAIL_EVENT_SOURCE,
)

SES_EMAIL_IDENTITY_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateEmailIdentity": _EMAIL_IDENTITY_UPSERT_MAPPING,
        "PutEmailIdentityDkimSigningAttributes": _EMAIL_IDENTITY_UPSERT_MAPPING,
        "PutEmailIdentityMailFromAttributes": _EMAIL_IDENTITY_UPSERT_MAPPING,
        "PutEmailIdentityFeedbackAttributes": _EMAIL_IDENTITY_UPSERT_MAPPING,
        "DeleteEmailIdentity": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_email_identity,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
