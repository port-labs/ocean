from collections.abc import Iterator
from typing import Any, TypeVar
from unittest.mock import MagicMock, patch

import pytest

from actions.abstract_executor import AbstractDevinExecutor
from actions.archive_session_executor import ArchiveSessionExecutor
from actions.create_session_executor import CreateSessionExecutor
from actions.exceptions import (
    DevinApiError,
    InvalidActionParametersException,
    SessionBusyError,
)
from actions.send_message_executor import SendMessageExecutor
from actions.terminate_session_executor import TerminateSessionExecutor
from core.tracking.tags import (
    MANAGED_TAG,
    build_external_id,
    external_id_tag,
    has_pending_tag,
    pending_tag,
    tracking_tags,
)
from tests.fakes import (
    INSTALLATION_ID,
    FakeDevin,
    FakePort,
    http_error,
    make_action_run,
    make_node_run,
    patched_ocean,
)

ExecutorT = TypeVar("ExecutorT", bound=AbstractDevinExecutor)

RUN_ID = "wfnr_1"
EXTERNAL_ID = build_external_id(RUN_ID)


@pytest.fixture
def devin() -> FakeDevin:
    return FakeDevin()


@pytest.fixture
def port() -> FakePort:
    return FakePort()


@pytest.fixture
def ocean_mock(port: FakePort) -> Iterator[MagicMock]:
    with patched_ocean(port) as mock_ocean:
        yield mock_ocean


def build(executor_class: type[ExecutorT], devin: FakeDevin) -> ExecutorT:
    with patch("actions.abstract_executor.create_devin_client", MagicMock()):
        executor = executor_class()
    executor.sessions = devin
    return executor


def own_tracking(tags: list[str]) -> list[str]:
    return [tag for tag in tags if tag.startswith("port:") and tag != MANAGED_TAG]


class TestCreateSession:
    async def test_tracked_session_is_tagged_at_creation(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        run = make_node_run(
            RUN_ID,
            "create_session",
            {"prompt": "Fix the bug", "repos": ["acme/api"], "tags": ["team:a"]},
        )

        await build(CreateSessionExecutor, devin).execute(run)

        tags = devin.last_create_body["tags"]
        assert tags[:2] == [MANAGED_TAG, "team:a"]
        assert pending_tag(INSTALLATION_ID) in tags
        assert external_id_tag(EXTERNAL_ID) in tags
        assert devin.last_create_body["repos"] == ["acme/api"]
        assert port.runs_by_external_id[EXTERNAL_ID] is run
        assert port.started[RUN_ID]["sessionId"] == "devin-1"
        assert "startedAt" in port.started[RUN_ID]
        assert RUN_ID not in port.completions
        ocean_mock.register_raw.assert_awaited_once()

    async def test_untracked_session_completes_immediately(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        run = make_action_run(
            RUN_ID, "create_session", {"prompt": "Hi", "reportCompletion": False}
        )

        await build(CreateSessionExecutor, devin).execute(run)

        assert devin.last_create_body["tags"] == [MANAGED_TAG]
        [completion] = port.completions[RUN_ID]
        assert completion.success
        assert completion.status_label == "Session created"

    async def test_typed_inputs_override_config(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        run = make_node_run(
            RUN_ID,
            "create_session",
            {
                "prompt": "typed",
                "config": {"prompt": "raw", "title": "From config", "tags": ["x"]},
            },
        )

        await build(CreateSessionExecutor, devin).execute(run)

        assert devin.last_create_body["prompt"] == "typed"
        assert devin.last_create_body["title"] == "From config"
        assert "x" in devin.last_create_body["tags"]

    @pytest.mark.parametrize(
        "properties",
        [
            {"prompt": "x", "tags": ["port:managed"]},
            {"prompt": "x", "config": {"tags": ["port:pending:other"]}},
        ],
    )
    async def test_reserved_tags_are_rejected(
        self,
        devin: FakeDevin,
        port: FakePort,
        ocean_mock: MagicMock,
        properties: dict[str, Any],
    ) -> None:
        run = make_node_run(RUN_ID, "create_session", properties)

        with pytest.raises(InvalidActionParametersException):
            await build(CreateSessionExecutor, devin).execute(run)
        assert devin.sessions == {}

    async def test_missing_prompt_is_rejected(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        run = make_node_run(RUN_ID, "create_session", {})

        with pytest.raises(InvalidActionParametersException, match="prompt"):
            await build(CreateSessionExecutor, devin).execute(run)

    async def test_known_user_is_resolved(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        devin.users["dev@acme.io"] = "user-1"
        run = make_node_run(
            RUN_ID,
            "create_session",
            {"prompt": "x", "createAsUserEmail": "dev@acme.io"},
        )

        await build(CreateSessionExecutor, devin).execute(run)

        assert devin.last_create_body["create_as_user_id"] == "user-1"

    async def test_unknown_user_falls_back_to_service_user(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        run = make_node_run(
            RUN_ID,
            "create_session",
            {"prompt": "x", "createAsUserEmail": "ghost@acme.io"},
        )

        await build(CreateSessionExecutor, devin).execute(run)

        assert "create_as_user_id" not in devin.last_create_body
        assert any("ghost@acme.io" in log for log in port.logs[RUN_ID])

    async def test_create_failure_raises_devin_error(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        executor = build(CreateSessionExecutor, devin)

        async def fail(body: dict[str, Any]) -> Any:
            raise http_error(400)

        devin.create = fail  # type: ignore[method-assign]
        run = make_node_run(RUN_ID, "create_session", {"prompt": "x"})

        with pytest.raises(DevinApiError, match="boom"):
            await executor.execute(run)
        assert RUN_ID not in port.started

    async def test_catalog_failure_does_not_fail_the_run(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        ocean_mock.register_raw.side_effect = RuntimeError("port is down")
        run = make_node_run(RUN_ID, "create_session", {"prompt": "x"})

        await build(CreateSessionExecutor, devin).execute(run)

        assert port.runs_by_external_id[EXTERNAL_ID] is run
        assert any("catalog" in log for log in port.logs[RUN_ID])


class TestSendMessage:
    def idle_session(self, devin: FakeDevin, tags: list[str] | None = None) -> None:
        devin.add_session(
            "devin-1",
            status="running",
            status_detail="waiting_for_user",
            tags=[MANAGED_TAG, *(tags or [])],
        )

    async def test_tags_are_written_before_the_message(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        self.idle_session(devin)
        tags_when_sent: list[str] = []
        original_send = devin.send_message

        async def send(session_id: str, body: dict[str, Any]) -> Any:
            tags_when_sent.extend(devin.tags(session_id))
            return await original_send(session_id, body)

        devin.send_message = send  # type: ignore[method-assign]
        run = make_node_run(
            RUN_ID, "send_message", {"sessionId": "devin-1", "message": "Go on"}
        )

        await build(SendMessageExecutor, devin).execute(run)

        assert pending_tag(INSTALLATION_ID) in tags_when_sent
        assert external_id_tag(EXTERNAL_ID) in tags_when_sent
        assert devin.last_message_body == {"message": "Go on"}
        assert port.runs_by_external_id[EXTERNAL_ID] is run
        assert RUN_ID not in port.completions

    async def test_untracked_message_completes_immediately(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        self.idle_session(devin)
        run = make_node_run(
            RUN_ID,
            "send_message",
            {"sessionId": "devin-1", "message": "hi", "reportCompletion": False},
        )

        await build(SendMessageExecutor, devin).execute(run)

        assert devin.tags("devin-1") == [MANAGED_TAG]
        [completion] = port.completions[RUN_ID]
        assert completion.success
        assert completion.status_label == "Message sent"

    async def test_session_with_a_waiting_run_is_busy(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        self.idle_session(
            devin, tags=tracking_tags("other-installation", "devin:wfnr_0", 1)
        )
        run = make_node_run(
            RUN_ID, "send_message", {"sessionId": "devin-1", "message": "hi"}
        )

        with pytest.raises(SessionBusyError):
            await build(SendMessageExecutor, devin).execute(run)
        assert devin.last_message_body == {}

    async def test_working_session_is_busy(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        devin.add_session("devin-1", status="running", status_detail="working")
        run = make_node_run(
            RUN_ID, "send_message", {"sessionId": "devin-1", "message": "hi"}
        )

        with pytest.raises(SessionBusyError):
            await build(SendMessageExecutor, devin).execute(run)

    async def test_tagging_failure_sends_nothing(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        self.idle_session(devin)
        devin.fail_append_tags = True
        run = make_node_run(
            RUN_ID, "send_message", {"sessionId": "devin-1", "message": "hi"}
        )

        with pytest.raises(DevinApiError, match="not sent"):
            await build(SendMessageExecutor, devin).execute(run)
        assert devin.last_message_body == {}

    async def test_send_failure_removes_tracking_tags(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        self.idle_session(devin, tags=["team:a"])
        devin.fail_send_message = True
        run = make_node_run(
            RUN_ID, "send_message", {"sessionId": "devin-1", "message": "hi"}
        )

        with pytest.raises(DevinApiError):
            await build(SendMessageExecutor, devin).execute(run)
        assert devin.tags("devin-1") == [MANAGED_TAG, "team:a"]

    async def test_missing_session_raises_devin_error(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        run = make_node_run(
            RUN_ID, "send_message", {"sessionId": "nope", "message": "hi"}
        )

        with pytest.raises(DevinApiError):
            await build(SendMessageExecutor, devin).execute(run)


class TestTerminateSession:
    async def test_waiting_run_is_failed_and_untracked(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        waiting = make_node_run("wfnr_waiting", "create_session", {})
        waiting_external_id = build_external_id(waiting.id)
        port.track(waiting, waiting_external_id)
        devin.add_session(
            "devin-1",
            tags=[
                MANAGED_TAG,
                "team:a",
                *tracking_tags(INSTALLATION_ID, waiting_external_id, 1),
            ],
        )
        run = make_node_run(
            RUN_ID, "terminate_session", {"sessionId": "devin-1", "archive": True}
        )

        await build(TerminateSessionExecutor, devin).execute(run)

        [waiting_completion] = port.completions[waiting.id]
        assert not waiting_completion.success
        assert waiting_completion.status_label == "Terminated"
        assert own_tracking(devin.tags("devin-1")) == []
        assert devin.sessions["devin-1"]["is_archived"] is True
        [completion] = port.completions[RUN_ID]
        assert completion.success

    async def test_finished_waiting_run_is_left_alone(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        waiting = make_node_run("wfnr_waiting", "create_session", {})
        waiting_external_id = build_external_id(waiting.id)
        port.track(waiting, waiting_external_id)
        port.in_progress[waiting.id] = False
        devin.add_session(
            "devin-1", tags=tracking_tags(INSTALLATION_ID, waiting_external_id, 1)
        )
        run = make_node_run(RUN_ID, "terminate_session", {"sessionId": "devin-1"})

        await build(TerminateSessionExecutor, devin).execute(run)

        assert waiting.id not in port.completions
        assert not has_pending_tag(devin.tags("devin-1"))

    async def test_untracked_session(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        devin.add_session("devin-1", tags=[MANAGED_TAG])
        run = make_node_run(RUN_ID, "terminate_session", {"sessionId": "devin-1"})

        await build(TerminateSessionExecutor, devin).execute(run)

        assert port.lookups == 0
        assert devin.sessions["devin-1"]["status"] == "exit"
        assert port.completions[RUN_ID][0].success


class TestArchiveSession:
    async def test_archives_and_completes(
        self, devin: FakeDevin, port: FakePort, ocean_mock: MagicMock
    ) -> None:
        devin.add_session("devin-1")
        run = make_node_run(RUN_ID, "archive_session", {"sessionId": "devin-1"})

        await build(ArchiveSessionExecutor, devin).execute(run)

        assert devin.sessions["devin-1"]["is_archived"] is True
        [completion] = port.completions[RUN_ID]
        assert completion.status_label == "Session archived"
        ocean_mock.register_raw.assert_awaited_once()


class TestPartitionKeys:
    @pytest.mark.parametrize(
        ("executor_class", "action", "expected"),
        [
            (CreateSessionExecutor, "create_session", None),
            (SendMessageExecutor, "send_message", "devin-1"),
            (TerminateSessionExecutor, "terminate_session", "devin-1"),
            (ArchiveSessionExecutor, "archive_session", "devin-1"),
        ],
    )
    async def test_partition_key(
        self,
        devin: FakeDevin,
        ocean_mock: MagicMock,
        executor_class: type[AbstractDevinExecutor],
        action: str,
        expected: str | None,
    ) -> None:
        run = make_node_run(RUN_ID, action, {"sessionId": "devin-1", "prompt": "x"})

        key = await build(executor_class, devin)._get_partition_key(run)

        assert key == expected
