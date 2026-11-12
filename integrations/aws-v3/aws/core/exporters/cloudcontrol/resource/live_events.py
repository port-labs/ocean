from aws.core.exporters.cloudcontrol.resource.models import (
    SingleCloudControlResourceRequest,
)
from aws.core.helpers.metadata.types import LiveEventContext, LiveEventFactories


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {"Identifier": context.identifier}


def cloud_control_live_events(type_name: str) -> LiveEventFactories:
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

    return LiveEventFactories(
        request_factory=request_factory,
        deletion_identifier_properties_factory=_deletion_identifier_properties,
    )
