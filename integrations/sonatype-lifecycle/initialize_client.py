from functools import lru_cache

from port_ocean.context.ocean import ocean

from sonatype.client import SonatypeClient


@lru_cache(maxsize=1)
def get_sonatype_client() -> SonatypeClient:
    """Create (once) and return a configured SonatypeClient.

    Values come from the integration configuration declared in
    ``.port/spec.yaml``; Ocean converts the camelCase config names into
    snake_case keys on ``ocean.integration_config``.
    """
    return SonatypeClient(
        base_url=ocean.integration_config["iq_server_url"],
        username=ocean.integration_config["iq_username"],
        token=ocean.integration_config["iq_user_token"],
    )
