from webhook_processors.utils import (
    discussion_id_from_payload,
    discussion_message_id,
    discussion_thread_id,
    timeline_entry_refs,
)


def test_discussion_id_from_payload_accepts_nested_and_top_level() -> None:
    assert (
        discussion_id_from_payload({"discussion": {"id": "disc_nested"}})
        == "disc_nested"
    )
    assert discussion_id_from_payload({"discussionId": "disc_top"}) == "disc_top"
    assert (
        discussion_id_from_payload(
            {"discussion": {"id": "disc_nested"}, "discussionId": "disc_top"}
        )
        == "disc_nested"
    )
    assert discussion_id_from_payload({}) is None


def test_discussion_thread_id_accepts_nested_and_top_level() -> None:
    assert (
        discussion_thread_id({"discussion": {"id": "disc_1", "threadId": "th_nested"}})
        == "th_nested"
    )
    assert discussion_thread_id({"threadId": "th_top"}) == "th_top"
    assert discussion_thread_id({"discussion": {"id": "disc_1"}}) is None


def test_timeline_entry_refs_uses_previous_entry_when_removed() -> None:
    assert timeline_entry_refs(
        {
            "changeType": "REMOVED",
            "timelineEntry": None,
            "previousTimelineEntry": {"id": "tl_old", "customerId": "c_1"},
        }
    ) == ("c_1", "tl_old")
    assert timeline_entry_refs(
        {"timelineEntry": {"id": "tl_new", "customerId": "c_2"}}
    ) == ("c_2", "tl_new")


def test_discussion_message_id_accepts_nested_and_top_level() -> None:
    assert discussion_message_id({"message": {"id": "dm_nested"}}) == "dm_nested"
    assert discussion_message_id({"messageId": "dm_top"}) == "dm_top"
    assert discussion_message_id({}) is None
