from typing import Any
from loguru import logger
from enum import StrEnum

from client import JenkinsClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"

    @staticmethod
    def get_object_kind_for_event(obj_type: str):
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
        ocean.integration_config["jenkins_password"],
    )


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received ${len(jobs)} jobs")
        yield jobs


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received ${len(jobs)} jobs")
        for job in jobs:
            async for builds in jenkins_client.get_builds(job["name"]):
                yield builds


@ocean.router.post("/events")
async def handle_events(event: dict[str, Any]) -> dict[str, bool]:
    logger.info(f'Received {event["dataType"]} event {event["id"]} | {event["type"]}')

    await ocean.register_raw(
        ObjectKind.get_object_kind_for_event(event["type"]), [event]
    )
    return {"ok": True}
