import asyncio
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from core.tracking.session_tracker import RUN_LOOKUP_GRACE_SECONDS, SessionTracker
from core.tracking.tags import (
    MANAGED_TAG,
    build_external_id,
    pending_tag,
    tracking_tags,
)
from tests.fakes import (
    INSTALLATION_ID,
    FakeDevin,
    FakePort,
    make_action_run,
    make_node_run,
    patched_ocean,
)

SENT_AT = 1_000
SESSION_ID = "devin-1"
RUN_ID = "wfnr_1"
EXTERNAL_ID = build_external_id(RUN_ID)


class Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def devin() -> FakeDevin:
    return FakeDevin()


@pytest.fixture
def port() -> FakePort:
    return FakePort()


@pytest.fixture
def clock() -> Clock:
    return Clock(SENT_AT + 60)


@pytest.fixture
def ocean_mock(port: FakePort) -> Iterator[MagicMock]:
    with patched_ocean(port) as mock_ocean:
        yield mock_ocean


def make_tracker(
    devin: FakeDevin, clock: Clock, max_hours: float = 72
) -> SessionTracker:
    return SessionTracker(
        sessions=devin,
        installation_id=INSTALLATION_ID,
        interval_seconds=30,
        max_hours=max_hours,
        clock=clock,
    )


def track_turn(
    devin: FakeDevin,
    port: FakePort,
    *,
    session_id: str = SESSION_ID,
    run_id: str = RUN_ID,
    sent_at: int = SENT_AT,
    action_run: bool = False,
    extra_tags: list[str] | None = None,
) -> None:
    external_id = build_external_id(run_id)
    tags = [
        MANAGED_TAG,
        *(extra_tags or []),
        *tracking_tags(INSTALLATION_ID, external_id, sent_at),
    ]
    if session_id in devin.sessions:
        devin.sessions[session_id]["tags"] = tags
    else:
        devin.add_session(session_id, tags=tags, updated_at=sent_at)
    run = (
        make_action_run(run_id, "create_session", {})
        if action_run
        else make_node_run(run_id, "create_session", {})
    )
    run_output = {"sessionId": session_id}
    if not action_run:
        run.output = run_output  # type: ignore[union-attr]
    port.track(run, external_id)


def message_logs(port: FakePort, run_id: str = RUN_ID) -> list[str]:
    return [line for line in port.logs.get(run_id, []) if line.startswith("[")]


def finish_turn(devin: FakeDevin, at: int, session_id: str = SESSION_ID) -> None:
    devin.add_message(session_id, "devin", "All done, opened a PR", at)
    devin.set_status(session_id, "running", "waiting_for_user", at)


@pytest.mark.usefixtures("ocean_mock")
class TestCompletion:
    async def test_completes_run_once_devin_finishes(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port, extra_tags=["team:payments"])
        devin.sessions[SESSION_ID]["pull_requests"] = [
            {"pr_url": "https://github.com/acme/app/pull/1", "pr_state": "open"}
        ]
        devin.sessions[SESSION_ID]["structured_output"] = {"answer": 42}
        finish_turn(devin, at=SENT_AT + 300)
        tracker = make_tracker(devin, clock)

        await tracker.tick()

        [completion] = port.completions[RUN_ID]
        assert completion.success is True
        assert completion.status_label == "Awaiting input"
        assert completion.output["pullRequests"] == [
            "https://github.com/acme/app/pull/1"
        ]
        assert completion.output["structuredOutput"] == {"answer": 42}
        assert completion.output["lastMessage"] == "All done, opened a PR"
        assert completion.output["acusConsumed"] == 1.5
        assert devin.tags(SESSION_ID) == [MANAGED_TAG, "team:payments"]

    async def test_reports_failure_for_failed_turn(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        devin.set_status(SESSION_ID, "suspended", "out_of_credits", SENT_AT + 10)

        await make_tracker(devin, clock).tick()

        [completion] = port.completions[RUN_ID]
        assert completion.success is False
        assert completion.status_label == "Usage limit"
        assert pending_tag(INSTALLATION_ID) not in devin.tags(SESSION_ID)

    async def test_in_progress_turn_only_updates_status_label_on_change(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        tracker = make_tracker(devin, clock)

        await tracker.tick()
        await tracker.tick()
        devin.set_status(SESSION_ID, "running", "waiting_for_approval", SENT_AT + 5)
        await tracker.tick()

        assert RUN_ID not in port.completions
        assert port.status_labels[RUN_ID] == ["Devin working", "Awaiting approval"]
        assert pending_tag(INSTALLATION_ID) in devin.tags(SESSION_ID)

    async def test_stale_ended_status_from_previous_turn_is_ignored(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        devin.add_session(
            SESSION_ID, status="running", status_detail="waiting_for_user"
        )
        devin.add_message(SESSION_ID, "devin", "previous turn answer", SENT_AT - 100)
        track_turn(devin, port)
        devin.add_message(SESSION_ID, "user", "follow-up", SENT_AT)
        devin.sessions[SESSION_ID]["updated_at"] = SENT_AT + 1

        tracker = make_tracker(devin, clock)
        await tracker.tick()
        assert RUN_ID not in port.completions

        finish_turn(devin, at=SENT_AT + 120)
        await tracker.tick()
        [completion] = port.completions[RUN_ID]
        assert completion.success is True
        assert completion.output["lastMessage"] == "All done, opened a PR"

    async def test_action_run_gets_summary_message(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port, action_run=True)
        devin.sessions[SESSION_ID]["pull_requests"] = [
            {"pr_url": "https://github.com/acme/app/pull/7", "pr_state": "open"}
        ]
        finish_turn(devin, at=SENT_AT + 30)

        await make_tracker(devin, clock).tick()

        [completion] = port.completions[RUN_ID]
        assert completion.message is not None
        assert "https://github.com/acme/app/pull/7" in completion.message
        assert "after 30s" in completion.message


@pytest.mark.usefixtures("ocean_mock")
class TestRestartRecovery:
    async def test_fresh_tracker_completes_sessions_tagged_before_it_started(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port, session_id="devin-1", run_id="wfnr_1")
        track_turn(devin, port, session_id="devin-2", run_id="wfnr_2")
        finish_turn(devin, at=SENT_AT + 50, session_id="devin-1")

        await make_tracker(devin, clock).tick()

        assert port.completions["wfnr_1"][0].success is True
        assert "wfnr_2" not in port.completions
        assert pending_tag(INSTALLATION_ID) in devin.tags("devin-2")

    async def test_other_installations_sessions_are_ignored(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        devin.add_session(
            "devin-9",
            tags=tracking_tags("other-installation", build_external_id("r_9"), SENT_AT),
            status="exit",
            updated_at=SENT_AT + 10,
        )

        await make_tracker(devin, clock).tick()

        assert port.completions == {}
        assert port.lookups == 0

    async def test_run_not_in_progress_strips_tags_without_reporting(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        port.in_progress[RUN_ID] = False

        await make_tracker(devin, clock).tick()

        assert RUN_ID not in port.completions
        assert devin.tags(SESSION_ID) == [MANAGED_TAG]

    async def test_missing_run_is_kept_during_grace_period_then_released(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        port.runs_by_external_id.clear()
        tracker = make_tracker(devin, clock)

        await tracker.tick()
        assert pending_tag(INSTALLATION_ID) in devin.tags(SESSION_ID)

        clock.now = SENT_AT + RUN_LOOKUP_GRACE_SECONDS + 1
        await tracker.tick()
        assert devin.tags(SESSION_ID) == [MANAGED_TAG]

    async def test_malformed_tracking_tags_are_stripped(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        devin.add_session(
            SESSION_ID, tags=[MANAGED_TAG, pending_tag(INSTALLATION_ID), "user-tag"]
        )

        await make_tracker(devin, clock).tick()

        assert devin.tags(SESSION_ID) == [MANAGED_TAG, "user-tag"]


@pytest.mark.usefixtures("ocean_mock")
class TestRobustness:
    async def test_expired_turn_times_out(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        clock.now = SENT_AT + 2 * 3600 + 1

        await make_tracker(devin, clock, max_hours=2).tick()

        [completion] = port.completions[RUN_ID]
        assert completion.success is False
        assert completion.status_label == "Timed out"
        assert completion.output["durationSeconds"] == 2 * 3600 + 1
        assert devin.tags(SESSION_ID) == [MANAGED_TAG]

    async def test_concurrent_ticks_report_once(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        finish_turn(devin, at=SENT_AT + 10)
        tracker = make_tracker(devin, clock)

        await asyncio.gather(tracker.tick(), tracker.tick())

        assert len(port.completions[RUN_ID]) == 1

    async def test_failed_tag_release_is_retried_without_reporting_twice(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        finish_turn(devin, at=SENT_AT + 10)
        devin.fail_replace_tags = 1
        tracker = make_tracker(devin, clock)

        await tracker.tick()
        assert pending_tag(INSTALLATION_ID) in devin.tags(SESSION_ID)

        await tracker.tick()
        assert devin.tags(SESSION_ID) == [MANAGED_TAG]
        assert len(port.completions[RUN_ID]) == 1

    async def test_failure_on_one_session_does_not_stop_others(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port, session_id="devin-1", run_id="wfnr_1")
        track_turn(devin, port, session_id="devin-2", run_id="wfnr_2")
        finish_turn(devin, at=SENT_AT + 10, session_id="devin-1")
        finish_turn(devin, at=SENT_AT + 10, session_id="devin-2")
        devin.fail_replace_tags = 1

        await make_tracker(devin, clock).tick()

        assert pending_tag(INSTALLATION_ID) in devin.tags("devin-1")
        assert devin.tags("devin-2") == [MANAGED_TAG]
        assert len(port.completions["wfnr_2"]) == 1


@pytest.mark.usefixtures("ocean_mock")
class TestSessionLogs:
    async def test_known_cursor_only_fetches_new_messages(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        devin.add_message(SESSION_ID, "user", "fix the bug", SENT_AT)
        tracker = make_tracker(devin, clock)

        await tracker.tick()
        devin.add_message(SESSION_ID, "devin", "Looking at it", SENT_AT + 5)
        await tracker.tick()

        assert devin.list_message_calls == [(SESSION_ID, None), (SESSION_ID, "1")]
        assert message_logs(port) == ["[user] fix the bug", "[devin] Looking at it"]

    async def test_backfill_after_restart_skips_previous_turns(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        devin.add_session(SESSION_ID, status="running", status_detail="working")
        devin.add_message(SESSION_ID, "user", "first turn", SENT_AT - 500)
        devin.add_message(SESSION_ID, "devin", "first answer", SENT_AT - 400)
        track_turn(devin, port)
        devin.add_message(SESSION_ID, "user", "second turn", SENT_AT)
        devin.add_message(SESSION_ID, "devin", "on it", SENT_AT + 1)

        await make_tracker(devin, clock).tick()

        assert message_logs(port) == ["[user] second turn", "[devin] on it"]

    async def test_idle_session_does_not_repost(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        devin.add_message(SESSION_ID, "devin", "working", SENT_AT + 1)
        tracker = make_tracker(devin, clock)

        await tracker.tick()
        await tracker.tick()
        await tracker.tick()

        assert port.logs[RUN_ID].count("[devin] working") == 1
        assert devin.list_message_calls[-1] == (SESSION_ID, "1")

    async def test_turn_state_is_dropped_once_completed(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        tracker = make_tracker(devin, clock)
        await tracker.tick()
        assert EXTERNAL_ID in tracker._turns

        finish_turn(devin, at=SENT_AT + 10)
        await tracker.tick()
        assert tracker._turns == {}

    async def test_log_posting_failure_does_not_block_completion(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port, session_id="devin-1", run_id="wfnr_1")
        track_turn(devin, port, session_id="devin-2", run_id="wfnr_2")
        finish_turn(devin, at=SENT_AT + 10, session_id="devin-1")
        finish_turn(devin, at=SENT_AT + 10, session_id="devin-2")
        port.fail_post_logs = True

        await make_tracker(devin, clock).tick()

        assert port.completions["wfnr_1"][0].success is True
        assert port.completions["wfnr_2"][0].success is True
        assert devin.tags("devin-1") == [MANAGED_TAG]

    async def test_message_fetch_failure_does_not_block_failed_turn(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        devin.set_status(SESSION_ID, "error", "error", SENT_AT + 10)
        devin.fail_list_messages = True

        await make_tracker(devin, clock).tick()

        assert port.completions[RUN_ID][0].success is False


@pytest.mark.usefixtures("ocean_mock")
class TestTimestamps:
    async def test_started_and_ended_at_come_from_tags_and_last_devin_message(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        devin.add_message(SESSION_ID, "devin", "progress", SENT_AT + 100)
        finish_turn(devin, at=SENT_AT + 250)
        clock.now = SENT_AT + 900

        await make_tracker(devin, clock).tick()

        output = port.completions[RUN_ID][0].output
        assert output["startedAt"] == "1970-01-01T00:16:40+00:00"
        assert output["endedAt"] == "1970-01-01T00:20:50+00:00"
        assert output["durationSeconds"] == 250
        assert any(
            line.startswith("Devin session ended at 1970-01-01T00:20:50+00:00")
            for line in port.logs[RUN_ID]
        )

    async def test_ended_at_falls_back_to_updated_at_without_devin_message(
        self, devin: FakeDevin, port: FakePort, clock: Clock
    ) -> None:
        track_turn(devin, port)
        devin.set_status(SESSION_ID, "error", "error", SENT_AT + 40)

        await make_tracker(devin, clock).tick()

        output = port.completions[RUN_ID][0].output
        assert output["durationSeconds"] == 40

    async def test_millisecond_timestamps_are_normalised(
        self, devin: FakeDevin, port: FakePort
    ) -> None:
        sent_at = 1_760_000_000
        track_turn(devin, port, sent_at=sent_at)
        devin.add_message(SESSION_ID, "devin", "done", (sent_at + 20) * 1000)
        devin.set_status(SESSION_ID, "running", "finished", (sent_at + 20) * 1000)

        await make_tracker(devin, Clock(sent_at + 60)).tick()

        assert port.completions[RUN_ID][0].output["durationSeconds"] == 20
