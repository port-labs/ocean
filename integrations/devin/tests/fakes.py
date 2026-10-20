"""In-memory stand-ins for the Devin API and Port's run API.

The tracker and executors are exercised against these rather than call-level
mocks so tests can assert on end state (tags left on a session, what a run
reported, which logs it got) the way a real restart would observe it.
"""

from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from clients.models import SessionMessage, SessionResponse
from core.sessions import DevinSessions
from port_ocean.core.models import (
    ActionRun,
    IntegrationRun,
    RunStatus,
    WorkflowNodeRun,
    WorkflowNodeRunLog,
    WorkflowNodeRunStatus,
)

INSTALLATION_ID = "devin-test"

OCEAN_MODULES = (
    "actions.abstract_executor.ocean",
    "actions.utils.ocean",
    "actions.create_session_executor.ocean",
    "actions.send_message_executor.ocean",
    "actions.terminate_session_executor.ocean",
    "actions.archive_session_executor.ocean",
    "core.catalog.ocean",
    "core.tracking.session_tracker.ocean",
)


def http_error(status_code: int = 500) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.devin.ai")
    response = httpx.Response(status_code, request=request, json={"detail": "boom"})
    return httpx.HTTPStatusError("boom", request=request, response=response)


class FakeDevin(DevinSessions):
    def __init__(self) -> None:
        super().__init__(MagicMock())
        self.sessions: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.users: dict[str, str] = {}
        self.clock = 1_000
        self.fail_replace_tags = 0
        self.fail_append_tags = False
        self.fail_send_message = False
        self.fail_list_messages = False
        self.list_message_calls: list[tuple[str, str | None]] = []
        self.last_create_body: dict[str, Any] = {}
        self.last_message_body: dict[str, Any] = {}
        self._next_id = 0

    def add_session(
        self,
        session_id: str,
        *,
        status: str = "running",
        status_detail: str | None = "working",
        tags: list[str] | None = None,
        updated_at: int | None = None,
    ) -> None:
        self.sessions[session_id] = {
            "session_id": session_id,
            "url": f"https://app.devin.ai/sessions/{session_id}",
            "status": status,
            "status_detail": status_detail,
            "tags": list(tags or []),
            "created_at": self.clock,
            "updated_at": self.clock if updated_at is None else updated_at,
            "acus_consumed": 1.5,
            "pull_requests": [],
            "org_id": "org-1",
        }
        self.messages.setdefault(session_id, [])

    def set_status(
        self, session_id: str, status: str, status_detail: str | None, at: int
    ) -> None:
        self.sessions[session_id].update(
            status=status, status_detail=status_detail, updated_at=at
        )

    def add_message(
        self, session_id: str, source: str, message: str, created_at: int
    ) -> None:
        self._next_id += 1
        self.messages[session_id].append(
            {
                "event_id": f"evt-{self._next_id}",
                "source": source,
                "message": message,
                "created_at": created_at,
            }
        )

    def tags(self, session_id: str) -> list[str]:
        return list(self.sessions[session_id]["tags"])

    def _response(self, session_id: str) -> SessionResponse:
        return SessionResponse.model_validate(dict(self.sessions[session_id]))

    async def create(self, body: dict[str, Any]) -> SessionResponse:
        self.last_create_body = body
        session_id = f"devin-{len(self.sessions) + 1}"
        self.add_session(session_id, status="new", status_detail=None)
        self.sessions[session_id]["tags"] = list(body.get("tags") or [])
        self.add_message(session_id, "user", body["prompt"], self.clock)
        return self._response(session_id)

    async def get(self, session_id: str) -> SessionResponse:
        if session_id not in self.sessions:
            raise http_error(404)
        return self._response(session_id)

    async def list_by_tag(
        self, tag: str
    ) -> AsyncGenerator[list[SessionResponse], None]:
        yield [
            self._response(session_id)
            for session_id, session in self.sessions.items()
            if tag in session["tags"]
        ]

    async def send_message(
        self, session_id: str, body: dict[str, Any]
    ) -> SessionResponse:
        if self.fail_send_message:
            raise http_error(500)
        self.last_message_body = body
        self.add_message(session_id, "user", body["message"], self.clock)
        self.sessions[session_id]["updated_at"] = self.clock
        return self._response(session_id)

    async def list_messages_after(
        self, session_id: str, after: str | None
    ) -> tuple[list[SessionMessage], str | None]:
        self.list_message_calls.append((session_id, after))
        if self.fail_list_messages:
            raise http_error(500)
        messages = self.messages[session_id]
        start = int(after) if after is not None else 0
        page = messages[start:]
        cursor = str(len(messages)) if page else after
        return [SessionMessage.model_validate(m) for m in page], cursor

    async def append_tags(self, session_id: str, tags: list[str]) -> list[str]:
        if self.fail_append_tags:
            raise http_error(500)
        current = self.sessions[session_id]["tags"]
        current.extend(tag for tag in tags if tag not in current)
        return list(current)

    async def replace_tags(self, session_id: str, tags: list[str]) -> list[str]:
        if self.fail_replace_tags:
            self.fail_replace_tags -= 1
            raise http_error(500)
        self.sessions[session_id]["tags"] = list(tags)
        return list(tags)

    async def terminate(self, session_id: str, archive: bool) -> SessionResponse:
        self.set_status(session_id, "exit", None, self.clock)
        self.sessions[session_id]["is_archived"] = archive
        return self._response(session_id)

    async def archive(self, session_id: str) -> SessionResponse:
        self.sessions[session_id]["is_archived"] = True
        return self._response(session_id)

    async def find_user_id_by_email(self, email: str) -> str | None:
        return self.users.get(email)


@dataclass
class Completion:
    success: bool
    message: str | None
    status_label: str | None
    output: dict[str, Any]


@dataclass
class FakePort:
    runs_by_external_id: dict[str, IntegrationRun] = field(default_factory=dict)
    in_progress: dict[str, bool] = field(default_factory=dict)
    logs: dict[str, list[str]] = field(default_factory=dict)
    status_labels: dict[str, list[str]] = field(default_factory=dict)
    completions: dict[str, list[Completion]] = field(default_factory=dict)
    started: dict[str, dict[str, Any]] = field(default_factory=dict)
    lookups: int = 0
    fail_post_logs: bool = False

    def track(self, run: IntegrationRun, external_id: str) -> None:
        self.runs_by_external_id[external_id] = run
        self.in_progress[run.id] = True

    async def find_run_by_external_id(self, external_id: str) -> IntegrationRun | None:
        self.lookups += 1
        return self.runs_by_external_id.get(external_id)

    def is_run_in_progress(self, run: IntegrationRun) -> bool:
        return self.in_progress.get(run.id, False)

    async def post_run_log(
        self,
        run: IntegrationRun,
        message: str,
        level: str = "INFO",
        status_label: str | None = None,
        should_raise: bool = False,
    ) -> None:
        self.logs.setdefault(run.id, []).append(message)
        if status_label:
            self.status_labels.setdefault(run.id, []).append(status_label)

    async def post_run_logs(
        self,
        run: IntegrationRun,
        logs: list[WorkflowNodeRunLog],
        should_raise: bool = False,
    ) -> None:
        if self.fail_post_logs:
            raise RuntimeError("port is down")
        self.logs.setdefault(run.id, []).extend(log.message for log in logs)

    async def update_run_started(
        self,
        run: IntegrationRun,
        link: str,
        external_id: str,
        extra_output: dict[str, Any] | None = None,
        status_label: str | None = None,
    ) -> None:
        self.track(run, external_id)
        self.started[run.id] = {"link": link, **(extra_output or {})}
        if isinstance(run, WorkflowNodeRun):
            run.output = {"workflowRunUrl": link, **(extra_output or {})}

    async def report_run_completed(
        self,
        run: IntegrationRun,
        success: bool,
        message: str | None = None,
        status_label: str | None = None,
        should_raise: bool = False,
    ) -> None:
        self.in_progress[run.id] = False
        output = dict(run.output) if isinstance(run, WorkflowNodeRun) else {}
        self.completions.setdefault(run.id, []).append(
            Completion(success, message, status_label, output)
        )


def make_node_run(
    run_id: str, action: str, properties: dict[str, Any]
) -> WorkflowNodeRun:
    return WorkflowNodeRun.parse_obj(
        {
            "identifier": run_id,
            "status": WorkflowNodeRunStatus.IN_PROGRESS,
            "config": {
                "type": "INTEGRATION_ACTION",
                "installationId": INSTALLATION_ID,
                "integrationProvider": "devin",
                "integrationInvocationType": action,
                "integrationActionExecutionProperties": properties,
            },
        }
    )


def make_action_run(run_id: str, action: str, properties: dict[str, Any]) -> ActionRun:
    return ActionRun.parse_obj(
        {
            "id": run_id,
            "status": RunStatus.IN_PROGRESS,
            "payload": {
                "type": "INTEGRATION_ACTION",
                "installationId": INSTALLATION_ID,
                "integrationActionType": action,
                "integrationActionExecutionProperties": properties,
            },
            "action": {"identifier": action},
        }
    )


@contextmanager
def patched_ocean(port: FakePort) -> Iterator[MagicMock]:
    mock_ocean = MagicMock()
    mock_ocean.port_client = port
    mock_ocean.config.integration.identifier = INSTALLATION_ID
    mock_ocean.register_raw = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    patches = [patch(module, mock_ocean) for module in OCEAN_MODULES]
    for module in ("core.catalog", "actions.abstract_executor"):
        patches.append(
            patch(
                f"{module}.event_context",
                MagicMock(side_effect=_noop_event_context),
            )
        )
    for p in patches:
        p.start()
    try:
        yield mock_ocean
    finally:
        for p in patches:
            p.stop()


class _NoopContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: Any) -> None:
        return None


def _noop_event_context(*args: Any, **kwargs: Any) -> _NoopContext:
    return _NoopContext()
