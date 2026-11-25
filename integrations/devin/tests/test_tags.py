from core.tracking.tags import (
    MANAGED_TAG,
    build_external_id,
    external_id_tag,
    has_pending_tag,
    parse_external_id,
    parse_sent_at,
    pending_tag,
    reserved_tags,
    sent_at_tag,
    strip_tracking_tags,
    tracking_tags,
)


def test_external_id_is_built_from_the_run_id() -> None:
    assert build_external_id("wfnr_abc") == "devin:wfnr_abc"


def test_external_id_round_trips_verbatim() -> None:
    external_id = build_external_id("r_123:with-colons")
    tags = ["user", external_id_tag(external_id)]
    assert parse_external_id(tags) == external_id


def test_sent_at_round_trips() -> None:
    assert parse_sent_at([sent_at_tag(1_760_000_000)]) == 1_760_000_000


def test_tracking_tags_contains_one_of_each() -> None:
    tags = tracking_tags("inst", "devin:r_1", 42)
    assert tags == [
        "port:pending:inst",
        "port:external-id:devin:r_1",
        "port:sent-at:42",
    ]


def test_missing_tags_parse_to_none() -> None:
    assert parse_external_id([MANAGED_TAG]) is None
    assert parse_sent_at([MANAGED_TAG]) is None


def test_malformed_tags_parse_to_none() -> None:
    assert parse_external_id(["port:external-id:"]) is None
    assert parse_sent_at(["port:sent-at:yesterday"]) is None
    assert parse_sent_at(["port:sent-at:-5"]) is None


def test_strip_keeps_managed_user_and_other_installations_tags() -> None:
    tags = [
        MANAGED_TAG,
        "team:payments",
        pending_tag("other"),
        *tracking_tags("mine", "devin:r_1", 42),
    ]
    assert strip_tracking_tags(tags, "mine") == [
        MANAGED_TAG,
        "team:payments",
        pending_tag("other"),
    ]


def test_has_pending_tag_matches_any_installation() -> None:
    assert has_pending_tag([pending_tag("other")])
    assert not has_pending_tag([MANAGED_TAG, "pending"])


def test_reserved_tags_flags_port_prefix() -> None:
    assert reserved_tags(["ok", "port:managed", "Port:x"]) == ["port:managed"]
