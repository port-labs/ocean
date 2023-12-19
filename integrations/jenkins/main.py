from typing import Any
from loguru import logger
from enum import StrEnum

from client import JenkinsClient
from port_ocean.context.ocean import ocean


class ObjectKind(StrEnum):
    JOB = "jenkinsJob"
    BUILD = "jenkinsBuild"

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
        ocean.integration_config["jenkins_token"],
    )


@ocean.on_resync()
async def on_resync(kind: str) -> None:
    jenkins_client = init_client()

    async for _jobs in jenkins_client.get_all_jobs_and_builds():
        if kind == ObjectKind.JOB:
            yield _jobs
        elif kind == ObjectKind.BUILD:
            yield [build for job in _jobs for build in job.get("builds", [])]


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
