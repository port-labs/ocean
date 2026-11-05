"""The only place Port's tracking tags on Devin sessions are encoded or parsed.

A session that a Port run is waiting on carries three tags:

- `port:pending:<installationId>`: the work-queue key. The tracker lists
  sessions by this single tag, server-side, on every tick, which also makes
  restart recovery automatic.
- `port:external-id:<externalId>`: the literal Port `externalRunId` passed to
  `update_run_started`, so the tracker can call `find_run_by_external_id`
  without rebuilding anything.
- `port:sent-at:<epochSeconds>`: when the turn started. Guards against reading
  the previous turn's ended status right after a follow-up message, bounds the
  run-log backfill after a restart, and is the `startedAt` of the run output.

`port:managed` is permanent and marks every session created from Port.
"""

RESERVED_PREFIX = "port:"
MANAGED_TAG = "port:managed"
PENDING_PREFIX = "port:pending:"
EXTERNAL_ID_PREFIX = "port:external-id:"
SENT_AT_PREFIX = "port:sent-at:"

EXTERNAL_RUN_ID_PREFIX = "devin:"


def build_external_id(run_id: str) -> str:
    """Port `externalRunId` for a run waiting on a Devin turn.

    Built from the run ID alone so it is known before the session exists, which
    lets `create_session` write every tracking tag in the create call itself.
    """
    return f"{EXTERNAL_RUN_ID_PREFIX}{run_id}"


def pending_tag(installation_id: str) -> str:
    return f"{PENDING_PREFIX}{installation_id}"


def external_id_tag(external_id: str) -> str:
    return f"{EXTERNAL_ID_PREFIX}{external_id}"


def sent_at_tag(epoch_seconds: int) -> str:
    return f"{SENT_AT_PREFIX}{epoch_seconds}"


def tracking_tags(installation_id: str, external_id: str, sent_at: int) -> list[str]:
    return [
        pending_tag(installation_id),
        external_id_tag(external_id),
        sent_at_tag(sent_at),
    ]


def has_pending_tag(tags: list[str]) -> bool:
    """Whether any installation is currently waiting on this session."""
    return any(tag.startswith(PENDING_PREFIX) for tag in tags)


def parse_external_id(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.startswith(EXTERNAL_ID_PREFIX):
            value = tag.removeprefix(EXTERNAL_ID_PREFIX)
            return value or None
    return None


def parse_sent_at(tags: list[str]) -> int | None:
    for tag in tags:
        if tag.startswith(SENT_AT_PREFIX):
            value = tag.removeprefix(SENT_AT_PREFIX)
            if value.isdigit():
                return int(value)
            return None
    return None


def strip_tracking_tags(tags: list[str], installation_id: str) -> list[str]:
    """Drop this installation's pending tag and the per-run tags.

    `port:managed`, user tags and other installations' pending tags survive.
    """
    own_pending = pending_tag(installation_id)
    return [
        tag
        for tag in tags
        if tag != own_pending
        and not tag.startswith(EXTERNAL_ID_PREFIX)
        and not tag.startswith(SENT_AT_PREFIX)
    ]


def reserved_tags(tags: list[str]) -> list[str]:
    """User-supplied tags that collide with the integration's namespace."""
    return [tag for tag in tags if tag.startswith(RESERVED_PREFIX)]
