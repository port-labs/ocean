from jenkins_integration.client import JenkinsClient
from jenkins_integration.types import JenkinsEvent, ObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger


def create_jenkins_client():
    logic_settings = ocean.integration_config
    return JenkinsClient(
        logic_settings["jenkins_host"],
        logic_settings["jenkins_user"],
        logic_settings["jenkins_password"],
    )

@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = create_jenkins_client()

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received {len(jobs)} jobs")
        yield jobs

@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = create_jenkins_client()

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received {len(jobs)} jobs")
        for job in jobs:
            builds = await jenkins_client.get_builds(job["data"]["name"])
            yield builds

@ocean.router.post("/events")
async def handle_events(event: JenkinsEvent) -> dict[str, bool]:
    with logger.contextualize(event_id=event.id, event_state=event.type):
        logger.info(
            f"{event.kind}: Received {event.dataType} event {event.id} | {event.type}"
        )

        if event.type in ["run.initialize", "run.started"]:
            return {"ok": True}

        event_record = event.dict(by_alias=True)

        await ocean.register_raw(event.kind, [event_record])
        return {"ok": True}