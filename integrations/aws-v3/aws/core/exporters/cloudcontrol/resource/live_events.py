from aws.core.exporters.cloudcontrol.resource.models import (
    SingleCloudControlResourceRequest,
)
from aws.core.helpers.metadata.types import LiveEventContext, LiveEventFactories


def build_cloud_control_live_events(type_name: str) -> LiveEventFactories:
    """Live-event factories for a custom kind, hydrated via Cloud Control GetResource.

    CloudTrail mappings live in ``aws.webhook.cloud_control_parser`` since they are
    shared by every Cloud Control type rather than registered per kind.
    """

    def request_factory(
        context: LiveEventContext, include_actions: list[str]
    ) -> SingleCloudControlResourceRequest:
        return SingleCloudControlResourceRequest(
            type_name=type_name,
            identifier=context.identifier,
            region=context.region,
            account_id=context.account_id,
            include=include_actions,
        )

    def deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
        return {"Identifier": context.identifier}

    return LiveEventFactories(
        request_factory=request_factory,
        deletion_identifier_properties_factory=deletion_identifier_properties,
    )
