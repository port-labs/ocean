from typing import cast
from loguru import logger

from client import JenkinsClient
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from overrides import JenkinStagesResourceConfig
from webhook.webhook_processors import BuildWebhookProcessor, JobWebhookProcessor
from utils import ObjectKind


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = JenkinsClient.create_from_ocean_configuration()

    async for jobs in jenkins_client.get_jobs():
        logger.info(f"Received batch with {len(jobs)} jobs")
        yield jobs


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = JenkinsClient.create_from_ocean_configuration()

    async for builds in jenkins_client.get_builds():
        logger.info(f"Received batch with {len(builds)} builds")
        yield builds


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = JenkinsClient.create_from_ocean_configuration()

    async for users in jenkins_client.get_users():
        logger.info(f"Received {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.STAGE)
async def on_resync_stages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    jenkins_client = JenkinsClient.create_from_ocean_configuration()
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


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jenkins integration")


ocean.add_webhook_processor("/webhook", BuildWebhookProcessor)
ocean.add_webhook_processor("/webhook", JobWebhookProcessor)
# DEPRECATED: The /events endpoint is deprecated and will be removed in a future version.
# Please use /webhook endpoint instead.
ocean.add_webhook_processor("/events", BuildWebhookProcessor)
ocean.add_webhook_processor("/events", JobWebhookProcessor)
