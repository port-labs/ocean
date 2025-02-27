from typing import Optional

from aiolimiter import AsyncLimiter
from snyk.client import SnykClient
from port_ocean.context.ocean import ocean

SNYK_MAX_REQUESTS_LIMIT_PER_HOUR = 1320
RATELIMITER = AsyncLimiter(SNYK_MAX_REQUESTS_LIMIT_PER_HOUR)


def init_client() -> SnykClient:
    def parse_list(value: str) -> Optional[list[str]]:
        return [item.strip() for item in value.split(",")] if value else None

    return SnykClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.app.base_url,
        parse_list(ocean.integration_config.get("organization_id", "")),
        parse_list(ocean.integration_config.get("groups", "")),
        ocean.integration_config.get("webhook_secret"),
        RATELIMITER,
    )
