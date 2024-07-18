from enum import StrEnum
from typing import Any

from port_ocean.context.ocean import ocean

from client.findings import get_findings
from client.auth import get_jwt_token


class ObjectKind(StrEnum):
    FINDING = "finding"


# TODO: Regenerate token every 24 hours / upon failure

@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    if kind == "finding":
        result = get_findings(get_token())
        return result["findings"]
    return []


def get_token():
    return get_jwt_token(
        ocean.integration_config.get("jit_client_id"),
        ocean.integration_config.get("jit_secret"),
    )


@ocean.on_start()
async def on_start() -> None:
    print("Starting Jit integration FTW")
