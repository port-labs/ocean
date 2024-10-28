import asyncio
import gc
from typing import Any, AsyncGenerator

import requests
from loguru import logger

import psutil
import os
import ctypes


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

        return []


if __name__ == "__main__":
    jira_client = JiraClient(
        jira_url=os.environ.get("OCEAN__INTEGRATION__CONFIG__JIRA_HOST"),
        jira_email=os.environ.get("OCEAN__INTEGRATION__CONFIG__ATLASSIAN_USER_EMAIL"),
        jira_token=os.environ.get("OCEAN__INTEGRATION__CONFIG__ATLASSIAN_USER_TOKEN"),
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(jira_client.get_paginated_issues())
