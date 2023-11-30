from loguru import logger

from core.client import JenkinsClient
from core.types import JenkinsEvent, ObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


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
            builds = await jenkins_client.get_builds(job["data"]["name"])
            yield builds


@ocean.router.post("/events")
async def handle_events(event: JenkinsEvent) -> dict[str, bool]:
    logger.info(
        f"{event.kind}: Received {event.dataType} event {event.id} | {event.type}"
    )

    if event.type in ["run.initialize", "run.started"]:
        return {"ok": True}

    event_record = event.dict(by_alias=True)

    await ocean.register_raw(event.kind, [event_record])
    return {"ok": True}
