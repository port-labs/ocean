from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.client import JenkinsClient
from core.types import JenkinsEvent, ObjectKind
from core.utils import sanitize_url


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logic_settings = ocean.integration_config
    jenkins_client = JenkinsClient(
        logic_settings["jenkins_host"],
        logic_settings["jenkins_user"],
        logic_settings["jenkins_password"],
    )

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received ${len(jobs)} jobs")
        yield jobs


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logic_settings = ocean.integration_config
    jenkins_client = JenkinsClient(
        logic_settings["jenkins_host"],
        logic_settings["jenkins_user"],
        logic_settings["jenkins_password"],
    )

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received ${len(jobs)} jobs")
        for job in jobs:
            builds = await jenkins_client.get_builds(job["data"]["name"])
            yield builds


@ocean.router.post("/events")
async def handle_events(event: JenkinsEvent) -> dict[str, bool]:
    with logger.contextualize(event_id=event.id, event_state=event.type):
        logger.info(f"{event.kind}: Received {event.dataType} event {event.id} | {event.type}")

        if event.type in ["run.initialize", "run.started"]:
            return {"ok": True}

        event_record = event.dict(by_alias=True)
        logger.info(event_record)

        print(event_record)
        await ocean.register_raw(event.kind, [event_record])
        return {"ok": True}


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
# @ocean.on_start()
# async def on_start() -> None:
#     # Something to do when the integration starts
#     # For example create a client to query 3rd party services - GitHub, Jira, etc...
#     print("Starting integration")
