"""Tests for ``aws.webhook.events`` dispatch tables."""

from aws.webhook.events import (
    CLOUDTRAIL_EVENT_NAME_TO_ACTION,
    CLOUDTRAIL_EVENT_NAME_TO_KIND,
    DETAIL_TYPE_TO_KIND,
    EC2_STATE_TO_ACTION,
    EventAction,
)


def test_dispatch_tables_keys_are_disjoint() -> None:
    """`DETAIL_TYPE_TO_KIND` keys must not overlap with
    `CLOUDTRAIL_EVENT_NAME_TO_KIND` keys, otherwise the router becomes
    ambiguous. Also: every key in `CLOUDTRAIL_EVENT_NAME_TO_ACTION` must
    have a corresponding entry in `CLOUDTRAIL_EVENT_NAME_TO_KIND`."""

    assert set(DETAIL_TYPE_TO_KIND.keys()).isdisjoint(
        CLOUDTRAIL_EVENT_NAME_TO_KIND.keys()
    )
    assert set(CLOUDTRAIL_EVENT_NAME_TO_ACTION.keys()).issubset(
        CLOUDTRAIL_EVENT_NAME_TO_KIND.keys()
    )


def test_ec2_state_action_mapping() -> None:
    assert EC2_STATE_TO_ACTION["running"] == EventAction.UPSERT
    assert EC2_STATE_TO_ACTION["terminated"] == EventAction.DELETE


def test_cloudtrail_action_mapping() -> None:
    assert (
        CLOUDTRAIL_EVENT_NAME_TO_ACTION["UpdateFunctionCode20150331"]
        == EventAction.UPSERT
    )
    assert (
        CLOUDTRAIL_EVENT_NAME_TO_ACTION["DeleteFunction20150331"] == EventAction.DELETE
    )
    assert CLOUDTRAIL_EVENT_NAME_TO_ACTION["CreateBucket"] == EventAction.UPSERT
    assert CLOUDTRAIL_EVENT_NAME_TO_ACTION["DeleteBucket"] == EventAction.DELETE
    assert CLOUDTRAIL_EVENT_NAME_TO_ACTION["DeleteService"] == EventAction.DELETE
    assert CLOUDTRAIL_EVENT_NAME_TO_ACTION["RunInstances"] == EventAction.UPSERT
