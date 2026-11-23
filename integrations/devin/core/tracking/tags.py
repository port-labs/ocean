RESERVED_PREFIX = "port:"
MANAGED_TAG = "port:managed"
PENDING_PREFIX = "port:pending:"
EXTERNAL_ID_PREFIX = "port:external-id:"
SENT_AT_PREFIX = "port:sent-at:"

EXTERNAL_RUN_ID_PREFIX = "devin:"


def build_external_id(run_id: str) -> str:
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
    own_pending = pending_tag(installation_id)
    return [
        tag
        for tag in tags
        if tag != own_pending
        and not tag.startswith(EXTERNAL_ID_PREFIX)
        and not tag.startswith(SENT_AT_PREFIX)
    ]


def reserved_tags(tags: list[str]) -> list[str]:
    return [tag for tag in tags if tag.startswith(RESERVED_PREFIX)]
