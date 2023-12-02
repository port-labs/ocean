from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from .client import JenkinsClient

BUILDS_BATCH_SIZE = 100

JOBS_BATCH_SIZE = 100


class ObjectKind:
    BUILD = "build"
    JOB = "job"


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logic_settings = ocean.integration_config
    jenkins_client = JenkinsClient(
        logic_settings["jenkins_username"],
        logic_settings["jenkins_password"],
        logic_settings["jenkins_host"],
    )

    logger.info("Retrieving Jenkins jobs")
    async for jobs in jenkins_client.get_jobs(JOBS_BATCH_SIZE):
        logger.info(f"Retrieved {len(jobs)} jobs from Jenkins")
        logger.info("Retrieving builds for jobs from Jenkins")
        for job in jobs:
            builds = [
                build
                async for build in jenkins_client.get_builds(
                    job["name"], BUILDS_BATCH_SIZE
                )
            ][0]
            logger.info(
                f"Retrieved {len(builds)} builds for job name: {job['name']} from Jenkins"
            )
            yield builds


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logic_settings = ocean.integration_config
    jenkins_client = JenkinsClient(
        logic_settings["jenkins_username"],
        logic_settings["jenkins_password"],
        logic_settings["jenkins_host"],
    )

    logger.info("Retrieving Jenkins jobs")
    async for jobs in jenkins_client.get_jobs(JOBS_BATCH_SIZE):
        logger.info(f"Retrieved {len(jobs)} jobs from Jenkins")
        yield jobs
