from typing import Any
from port_ocean.context.ocean import ocean
from client import JenkinsClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger
from enum import StrEnum


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"


def init_client() -> JenkinsClient:
    """
    Intialize Jenkins Client
    """
    config = ocean.integration_config

    jenkins_client = JenkinsClient(
                        config["jenkins_host"],
                        config["jenkins_username"],
                        config["jenkins_token"])

    return jenkins_client


@ocean.on_resync(ObjectKind.JOB)
async def resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client()

    async for jobs in jenkins_client.get_paginated_jobs():
        logger.info(f"Received {len(jobs)} jobs from Jenkins")
        yield jobs

    await jenkins_client.close()



@ocean.on_resync(ObjectKind.BUILD)
async def resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = init_client() 

    async for jobs in jenkins_client.get_paginated_jobs():
        for job in jobs:
            async for builds in jenkins_client.get_paginated_builds(job['url']):
                logger.info(f"Received {len(builds)} builds for job {job['name']} from Jenkins")
                yield builds

    await jenkins_client.close()