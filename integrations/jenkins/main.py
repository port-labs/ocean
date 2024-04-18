from typing import Any
from loguru import logger
from enum import StrEnum

from client import JenkinsClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_RESULT


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"
    USER = "user"

    @staticmethod
    def get_object_kind_for_event(obj_type: str) -> str | None:
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


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> RAW_RESULT:

    for j in range(1):
        jobs = []
        for i in range(10):
            jobs.append(
                {
                    "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
                    "buildable": True,
                    "color": "blue",
                    "displayName": f"{j}yes{i}",
                    "fullName": f"{j}-yes{i}",
                    "name": f"{j}-yes{i}",
                    "url": f"http://my-jenkins:8080/job/{j}yes{i}/",
                }
            )
        yield jobs


@ocean.on_resync(ObjectKind.BUILD)
async def on_resync_builds(kind: str) -> RAW_RESULT:
    return []


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> RAW_RESULT:
    return []


@ocean.router.post("/events")
async def handle_events(event: dict[str, Any]) -> dict[str, bool]:

    await ocean.register_raw(
        "job",
        [
            {
                "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
                "buildable": True,
                "color": "blue",
                "displayName": event.get("name"),
                "fullName": event.get("name"),
                "name": event.get("name"),
                "url": f"http://my-jenkins:8080/job/{event.get('name')}/",
            }
        ],
    )

    logger.info("Webhook event processed")
    return {"ok": True}
