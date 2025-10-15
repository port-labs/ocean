from enum import StrEnum


class ObjectKind(StrEnum):
    """Okta object kinds used across the integration."""

    USER = "okta-user"
    GROUP = "okta-group"


class OktaEventType(StrEnum):
    """Okta System Log event types used for Event Hooks subscription and processing."""

    GROUP_LIFECYCLE_CREATE = "group.lifecycle.create"
    GROUP_LIFECYCLE_DELETE = "group.lifecycle.delete"
    GROUP_PROFILE_UPDATE = "group.profile.update"
    GROUP_USER_MEMBERSHIP_ADD = "group.user_membership.add"
    GROUP_USER_MEMBERSHIP_REMOVE = "group.user_membership.remove"

    USER_ACCOUNT_UPDATE_PROFILE = "user.account.update_profile"
    USER_LIFECYCLE_CREATE = "user.lifecycle.create"
    USER_LIFECYCLE_DEACTIVATE = "user.lifecycle.deactivate"
    USER_LIFECYCLE_ACTIVATE = "user.lifecycle.activate"
    USER_LIFECYCLE_DELETE_INITIATED = "user.lifecycle.delete.initiated"
    USER_LIFECYCLE_REACTIVATE = "user.lifecycle.reactivate"
    USER_LIFECYCLE_SUSPEND = "user.lifecycle.suspend"
    USER_LIFECYCLE_UNSUSPEND = "user.lifecycle.unsuspend"


def default_event_subscriptions() -> list[str]:
    """Default list of event types to subscribe to for Okta Event Hooks."""
    return [
        OktaEventType.GROUP_LIFECYCLE_CREATE.value,
        OktaEventType.GROUP_LIFECYCLE_DELETE.value,
        OktaEventType.GROUP_PROFILE_UPDATE.value,
        OktaEventType.GROUP_USER_MEMBERSHIP_ADD.value,
        OktaEventType.GROUP_USER_MEMBERSHIP_REMOVE.value,
        OktaEventType.USER_ACCOUNT_UPDATE_PROFILE.value,
        OktaEventType.USER_LIFECYCLE_CREATE.value,
        OktaEventType.USER_LIFECYCLE_DEACTIVATE.value,
        OktaEventType.USER_LIFECYCLE_ACTIVATE.value,
        # Current default in client uses initiated; include that here
        OktaEventType.USER_LIFECYCLE_DELETE_INITIATED.value,
        OktaEventType.USER_LIFECYCLE_REACTIVATE.value,
        OktaEventType.USER_LIFECYCLE_SUSPEND.value,
        OktaEventType.USER_LIFECYCLE_UNSUSPEND.value,
    ]
