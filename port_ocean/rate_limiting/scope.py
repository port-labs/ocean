from port_ocean.context.ocean import ocean


def rate_limit_org_scope(override: str | None = None) -> str:
    if override:
        return override
    try:
        return ocean.config.port.client_id
    except Exception:
        return "unknown"


def rate_limit_integration_id() -> str:
    try:
        return ocean.config.integration.identifier
    except Exception:
        return "unknown"
