from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from jenkins_integration.core.client import JenkinsClient
from jenkins_integration.core.types import ObjectKind
from jenkins_integration.utils import retrieve_batch_size_config_value


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logic_settings = ocean.integration_config
    jenkins_client = JenkinsClient(
        logic_settings["jenkins_username"],
        logic_settings["jenkins_password"],
        logic_settings["jenkins_host"],
    )

    BUILDS_BATCH_SIZE = retrieve_batch_size_config_value(
        logic_settings, "jenkins_builds_batch_size", 100
    )

    JOBS_BATCH_SIZE = retrieve_batch_size_config_value(
        logic_settings, "jenkins_jobs_batch_size", 100
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

    JOBS_BATCH_SIZE = retrieve_batch_size_config_value(
        logic_settings, "jenkins_jobs_batch_number", 100
    )

    logger.info("Retrieving Jenkins jobs")
    async for jobs in jenkins_client.get_jobs(JOBS_BATCH_SIZE):
        logger.info(f"Retrieved {len(jobs)} jobs from Jenkins")
        yield jobs
