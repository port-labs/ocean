from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationFeatureFlag


async def is_aws_v3_custom_kinds_enabled() -> bool:
    """Return whether arbitrary Cloud Control resource kinds are enabled for this org."""
    try:
        flags = await ocean.port_client.get_organization_feature_flags(
            should_raise=False,
            should_log=False,
        )
        return IntegrationFeatureFlag.AWS_V3_CUSTOM_KINDS_ENABLED in flags
    except Exception as e:
        logger.bind(local_only=True).warning(
            f"Failed to check AWS v3 custom kinds feature flag, assuming disabled: {e}"
        )
        return False
