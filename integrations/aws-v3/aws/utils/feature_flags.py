from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationFeatureFlag


async def is_aws_v3_live_events_enabled() -> bool:
    """Return whether AWS-v3 CloudTrail live events are enabled for this org."""
    try:
        flags = await ocean.port_client.get_organization_feature_flags()
        return IntegrationFeatureFlag.AWS_V3_LIVE_EVENTS_ENABLED in flags
    except Exception as error:
        logger.warning(
            "Failed to check AWS-v3 live events feature flag, assuming disabled",
            error=str(error),
        )
        return False
