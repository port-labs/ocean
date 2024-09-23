from typing import Any, cast
from loguru import logger
from enum import StrEnum

from client import JenkinsClient
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from overrides import JenkinStagesResourceConfig


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"
    USER = "user"
    STAGE = "stage"

    @staticmethod
    def get_object_kind_for_event(obj_type: str) -> str | None:
        if obj_type.startswith("item"):
            return ObjectKind.JOB
        elif obj_type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None


def init_client() -> JenkinsClient:
    logger.info(f"Initializing JenkinsClient {ocean.integration_config}")
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


@ocean.on_resync(ObjectKind.STAGE)
async def on_resync_stages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()
    stages_count = 0
    max_stages = 10000

    stages_selector = cast(JenkinStagesResourceConfig, event.resource_config)
    job_url = stages_selector.selector.job_url

    logger.info(f"Syncing stages for job {job_url}")

    async for stages in jenkins_client.get_stages(job_url):
        logger.info(f"Received batch with {len(stages)} stages")
        if stages_count + len(stages) > max_stages:
            stages = stages[: max_stages - stages_count]
            yield stages
            logger.warning(
                f"Reached the maximum limit of {max_stages} stages. Skipping the remaining stages."
            )
            return
        stages_count += len(stages)
        yield stages

    logger.info(f"Total stages synced: {stages_count}")


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
