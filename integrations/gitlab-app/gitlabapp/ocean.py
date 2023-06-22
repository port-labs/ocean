from typing import Any, Dict, List

from gitlabapp.bootstrap import setup_application
from gitlabapp.events.event_handler import EventHandler
from gitlabapp.ocean_helper import get_all_projects, get_all_services
from port_ocean.context.event import event_context
from port_ocean.context.ocean import ocean
from starlette.requests import Request


@ocean.router.post("/hook/{group_id}")
async def handle_webhook(group_id: str, request: Request):
    event_id = f'{request.headers.get("X-Gitlab-Event")}:{group_id}'
    await request.json()
    async with event_context(event_id):
        await EventHandler().notify(event_id, group_id, request)
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    setup_application()


@ocean.on_resync("project")
async def on_resync(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    projects = get_all_projects(all_tokens_services)
    return projects


@ocean.on_resync("mergeRequest")
async def resync_merge_requests(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    root_groups = sum(
        [service.get_root_groups() for service in all_tokens_services], []
    )
    return [
        merge_request.asdict()
        for group in root_groups
        for merge_request in group.mergerequests.list(scope="all")
    ]


@ocean.on_resync("issues")
async def resync_issues(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    root_groups = sum(
        [service.get_root_groups() for service in all_tokens_services], []
    )
    return [issue.asdict() for group in root_groups for issue in group.issues.list()]
