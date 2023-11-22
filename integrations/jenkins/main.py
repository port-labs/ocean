from enum import StrEnum
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from .utils import JenkinsConnector


class ObjectKind(StrEnum):
    BUILD = "build"
    JOB = "job"


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for jobs in JenkinsConnector().get_jenkins_jobs():
        logger.info(f"Received ${len(jobs)} jobs")
        yield jobs


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for jobs in JenkinsConnector().get_jenkins_jobs():
        logger.info(f"Received ${len(jobs)} jobs")

        for job in jobs:
            builds = await JenkinsConnector().get_jenkins_builds(job)
            yield builds