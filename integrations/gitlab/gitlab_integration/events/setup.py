from typing import Type, List

from gitlab import Gitlab

from gitlab_integration.events.event_handler import EventHandler, SystemEventHandler
from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.events.hooks.issues import Issues
from gitlab_integration.events.hooks.jobs import Job
from gitlab_integration.events.hooks.merge_request import MergeRequest
from gitlab_integration.events.hooks.pipelines import Pipelines
from gitlab_integration.events.hooks.push import PushHook
from gitlab_integration.events.hooks.group import GroupHook
from gitlab_integration.gitlab_service import GitlabService
from port_ocean.exceptions.core import OceanAbortException


class TokenNotFoundException(OceanAbortException):
    pass


class TooManyTokensException(OceanAbortException):
    def __init__(self):
        super().__init__(
            "There are too many tokens in tokenMapping. When useSystemHook = true,"
            / " there should be only one token configured"
        )


class EventListenerConflict(OceanAbortException):
    pass


event_handler = EventHandler()
system_event_handler = SystemEventHandler()


def validate_hooks_override_config(
    token_mapping: dict[str, list[str]],
    token_group_override_hooks_mapping: dict[str, list[str]],
    use_system_hook: bool,
) -> None:
    if len(token_mapping.keys()) == 0:
        raise TokenNotFoundException("There must be at least one token in tokenMapping")

    if use_system_hook:
        if len(token_mapping.keys()) == 1:
            return
        else:
            raise TooManyTokensException()

    if not token_group_override_hooks_mapping:
        return

    groups_paths: list[str] = []
    for token in token_group_override_hooks_mapping:
        if token not in token_mapping:
            raise TokenNotFoundException(
                "Tokens from tokenGroupHooksOverrideMapping should also be in tokenMapping"
            )
        groups_paths.extend(token_group_override_hooks_mapping[token])

    for group_path in groups_paths:
        if groups_paths.count(group_path) > 1:
            raise EventListenerConflict(
                f"Cannot listen to the same group multiple times. group: {group_path}"
            )
        for second_group_path in groups_paths:
            if second_group_path != group_path and second_group_path.startswith(
                group_path
            ):
                raise EventListenerConflict(
                    "Cannot listen to multiple groups with hierarchy to one another."
                    f" Group: {second_group_path} is inside group: {group_path}"
                )


def setup_listeners(gitlab_service: GitlabService, webhook_id: str | int) -> None:
    handlers = [
        PushHook(gitlab_service),
        MergeRequest(gitlab_service),
        Job(gitlab_service),
        Issues(gitlab_service),
        Pipelines(gitlab_service),
        GroupHook(gitlab_service),
    ]
    for handler in handlers:
        event_ids = [f"{event_name}:{webhook_id}" for event_name in handler.events]
        event_handler.on(event_ids, handler.on_hook)


def setup_system_listeners(gitlab_clients: list[GitlabService]) -> None:
    handlers: List[Type[HookHandler]] = [
        PushHook,
        MergeRequest,
        Job,
        Issues,
        Pipelines,
        GroupHook,
    ]
    for handler in handlers:
        system_event_handler.on(handler)

    for gitlab_service in gitlab_clients:
        system_event_handler.add_client(gitlab_service)


def listen_to_webhook_by_token(
    gitlab_host: str,
    app_host: str,
    use_system_hook: bool,
    token: str,
    token_group_override_hooks_mapping: dict[str, list[str]],
    group_mapping: list[str],
) -> GitlabService:
    gitlab_client = Gitlab(gitlab_host, token)
    gitlab_service = GitlabService(gitlab_client, app_host, group_mapping)
    if use_system_hook:
        gitlab_service.create_system_hook()
    else:
        groups_for_webhooks = gitlab_service.get_filtered_groups_for_webhooks(
            token_group_override_hooks_mapping, token
        )
        webhook_ids = gitlab_service.create_webhooks(groups_for_webhooks)
        for webhook_id in webhook_ids:
            setup_listeners(gitlab_service, webhook_id)
    return gitlab_service


def setup_application(
    token_mapping: dict[str, list[str]],
    gitlab_host: str,
    app_host: str,
    use_system_hook: bool,
    token_group_override_hooks_mapping: dict[str, list[str]],
) -> None:
    validate_hooks_override_config(
        token_mapping, token_group_override_hooks_mapping, use_system_hook
    )
    clients = []
    for token, group_mapping in token_mapping.items():
        clients.append(
            listen_to_webhook_by_token(
                gitlab_host,
                app_host,
                use_system_hook,
                token,
                token_group_override_hooks_mapping,
                group_mapping,
            )
        )
    if use_system_hook:
        setup_system_listeners(clients)
