from gitlabapp.bootstrap import setup_application
from gitlabapp.events.event_handler import EventHandler
from gitlabapp.ocean_helper import get_all_projects, get_all_services
from port_ocean.context.event import event_context
from port_ocean.context.integration import ocean
from port_ocean.types import RawObjectDiff
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


@ocean.on_resync()
async def on_resync(kind: str) -> RawObjectDiff:
    all_tokens_services = get_all_services()

    if kind == "project":
        projects = get_all_projects(all_tokens_services)
        return {
            "before": [],
            "after": projects,
        }

    # ToDo: allow returning None
    return {
        "before": [],
        "after": [],
    }
