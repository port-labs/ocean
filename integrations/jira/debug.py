import asyncio
import ctypes
import gc
import os
import sys
import threading
from asyncio import ensure_future
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Any

import psutil
import requests
import uvicorn
from fastapi import FastAPI
from loguru import logger

from jira.client import JiraClient
from jira.overrides import JiraPortAppConfig
from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.core.defaults import initialize_defaults
from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.run import _get_default_config_factory
from port_ocean.utils.repeat import repeat_every
from port_ocean.utils.signal import signal_handler
from port_ocean.version import __integration_version__

PAGE_SIZE = 50

class Ocean:
    def __init__(
        self,
        app: Any | None = None,
        integration_class: Any | None = None,
        integration_router: Any | None = None,
        config_factory: Any | None = None,
        config_override: Any | None = None,
    ):
        initialize_port_ocean_context(self)
        self.fast_api_app = app or FastAPI()
        # self.fast_api_app.middleware("http")(request_handler)

        self.config = IntegrationConfiguration(
            # type: ignore
            _integration_config_model=config_factory,
            **(config_override or {}),
        )

        # self.integration_router = integration_router or APIRouter()

        self.port_client = PortClient(
            base_url=self.config.port.base_url,
            client_id=self.config.port.client_id,
            client_secret=self.config.port.client_secret,
            integration_identifier=self.config.integration.identifier,
            integration_type=self.config.integration.type,
            integration_version=__integration_version__,
        )
        self.integration = (
            integration_class(ocean) if integration_class else BaseIntegration(ocean)
        )

        # self.resync_state_updater = ResyncStateUpdater(
        #     self.port_client, self.config.scheduled_resync_interval
        # )

    async def _setup_scheduled_resync(
        self,
    ) -> None:
        async def execute_resync_all() -> None:
            # await self.resync_state_updater.update_before_resync()
            logger.info("Starting a new scheduled resync")
            try:
                await self.integration.sync_raw_all()
                # await self.resync_state_updater.update_after_resync()
            except asyncio.CancelledError:
                logger.warning(
                    "resync was cancelled by the scheduled resync, skipping state update"
                )
            # except Exception as e:
            #     await self.resync_state_updater.update_after_resync(
            #         IntegrationStateStatus.Failed
            #     )
            #     raise e

        interval = self.config.scheduled_resync_interval
        loop = asyncio.get_event_loop()
        if interval is not None:
            logger.info(
                f"Setting up scheduled resync, the integration will automatically perform a full resync every {interval} minutes)",
                scheduled_interval=interval,
            )
            repeated_function = repeat_every(
                seconds=interval * 60,
                # Not running the resync immediately because the event listener should run resync on startup
                wait_first=True,
            )(
                lambda: threading.Thread(
                    target=lambda: asyncio.run_coroutine_threadsafe(
                        execute_resync_all(), loop
                    )
                ).start()
            )
            await repeated_function()

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        # self.fast_api_app.include_router(self.integration_router, prefix="/integration")

        @asynccontextmanager
        async def lifecycle(_: Any) -> Any:
            try:
                await self.integration.start()
                ensure_future(asyncio.create_task(self.integration.sync_raw_all()))
                await self._setup_scheduled_resync()
                yield None
            except Exception:
                logger.exception("Integration had a fatal error. Shutting down.")
                sys.exit("Server stopped")
            finally:
                signal_handler.exit()

        self.fast_api_app.router.lifespan_context = lifecycle
        await self.fast_api_app(scope, receive, send)

class JiraIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = JiraPortAppConfig

config_factory = _get_default_config_factory()
app = Ocean(
    integration_class=JiraIntegration,
    config_factory=config_factory,
    config_override={},
)
initialize_defaults(app.integration.AppConfigHandlerClass.CONFIG_CLASS, app.config)

PAGE_SIZE = 50


class JiraClient:
    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token
        self.jira_api_auth = (self.jira_email, self.jira_token)

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.client = requests.session()
        self.client.auth = self.jira_api_auth

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = 0, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

    async def _get_paginated_issues(self, params: dict[str, Any]) -> dict[str, Any]:
        issue_response = await asyncio.to_thread(
            self.client.get, f"{self.api_url}/search", params=params
        )
        try:
            issue_response.raise_for_status()
            return issue_response.json()
        except Exception:
            return {"issues": [], "total": 0}

    def print_process_info(self):
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim.restype = ctypes.c_int
        libc.malloc_trim.argtypes = [ctypes.c_size_t]

        libc.malloc_stats.restype = None
        libc.malloc_stats()

        class MallInfo(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_int)
                for name in (
                    "arena",
                    "ordblks",
                    "smblks",
                    "hblks",
                    "hblkhd",
                    "usmblks",
                    "fsmblks",
                    "uordblks",
                    "fordblks",
                    "keepcost",
                )
            ]

        mallinfo = libc.mallinfo
        mallinfo.argtypes = []
        mallinfo.restype = MallInfo

        info = mallinfo()
        fields = [(name, getattr(info, name)) for name, _ in info._fields_]
        print("Malloc info:")
        for name, value in fields:
            print(f"- {name}: {value}")

        process = psutil.Process(os.getpid())
        print(f"Open files: {len(process.open_files())}")
        print(f"Active Connections: {len(process.connections())}")
        print(f"Number of threads: {process.num_threads()}")
        print(
            f"Number of active coroutines: {len(asyncio.all_tasks(asyncio.get_event_loop()))}"
        )
        print(f"RSS before trim: {process.memory_info().rss / 1024 ** 2} MB")
        libc.malloc_trim(0)  # Pass 0 to trim all possible memory
        print(f"RSS after trim: {process.memory_info().rss / 1024 ** 2} MB")
        gc.collect()
        print(f"RSS after gc collect: {process.memory_info().rss / 1024 ** 2} MB")

    async def get_paginated_issues(self) -> list[dict[str, Any]]:
        logger.info("Getting issues from Jira")

        params = self._generate_base_req_params()

        total_issues = (await self._get_paginated_issues(params))["total"]

        if total_issues == 0:
            logger.warning(
                "Issue query returned 0 issues, did you provide the correct Jira API credentials and JQL query?"
            )

        params["maxResults"] = PAGE_SIZE
        while params["startAt"] <= total_issues:
            logger.info(f"Current query position: {params['startAt']}/{total_issues}")
            issue_response_list = (await self._get_paginated_issues(params))["issues"]
            # yield issue_response_list
            self.print_process_info()
            params["startAt"] += PAGE_SIZE
            if params["startAt"] > total_issues:
                params["startAt"] = 0

        yield []


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    logic_settings = app.integration.integration_config
    app_host = logic_settings.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Jira"
        )
        return

    jira_client = JiraClient(
        logic_settings["jira_host"],
        logic_settings["atlassian_user_email"],
        logic_settings["atlassian_user_token"],
    )

    await jira_client.create_events_webhook(
        logic_settings["app_host"],
    )


# async def on_resync_projects(kind: str) -> Any:
#     client = JiraClient(
#         app.config.integration.config.dict()["jira_host"],
#         app.config.integration.config.dict()["atlassian_user_email"],
#         app.config.integration.config.dict()["atlassian_user_token"],
#     )
#
#     async for projects in client.get_paginated_projects():
#         logger.info(f"Received project batch with {len(projects)} issues")
#         yield projects
# app.integration.on_resync(on_resync_projects, ObjectKind.PROJECT)

async def on_resync_issues(kind: str) -> Any:
    client = JiraClient(
        app.config.integration.config.dict()["jira_host"],
        app.config.integration.config.dict()["atlassian_user_email"],
        app.config.integration.config.dict()["atlassian_user_token"],
    )

    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues
app.integration.on_resync(on_resync_issues, ObjectKind.ISSUE)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # loop.run_until_complete(app.integration.start())
    # loop.run_until_complete(app.integration.sync_raw_all())
