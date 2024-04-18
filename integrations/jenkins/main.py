from typing import Any
from loguru import logger
from enum import StrEnum

from client import JenkinsClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"
    USER = "user"

    @staticmethod
    def get_object_kind_for_event(obj_type: str) -> str | None:
        if obj_type.startswith("item"):
            return ObjectKind.JOB
        elif obj_type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None


def init_client() -> JenkinsClient:
    return JenkinsClient(
        ocean.integration_config["jenkins_host"],
        ocean.integration_config["jenkins_user"],
        ocean.integration_config["jenkins_token"],
    )


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received batch with {len(jobs)} jobs")
        yield jobs


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()

    async for builds in jenkins_client.get_builds():
        logger.info(f"Received batch with {len(builds)} builds")
        yield builds


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()

    async for users in jenkins_client.get_users():
        logger.info(f"Received {len(users)} users")
        yield users


@ocean.router.post("/events")
async def handle_events(event: dict[str, Any]) -> dict[str, bool]:
    jenkins_client = init_client()
    logger.info(f'Received {event["dataType"]} event {event["id"]} | {event["type"]}')

    kind = ObjectKind.get_object_kind_for_event(event["type"])

    if kind:
        resource = await jenkins_client.get_single_resource(event["url"])
        await ocean.register_raw(kind, [resource])

    logger.info("Webhook event processed")
    return {"ok": True}
