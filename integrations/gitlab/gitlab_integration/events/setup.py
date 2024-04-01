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
from gitlab_integration.utils import merge_all_groups
from gitlab_integration.errors import (
    GitlabTokenNotFoundException,
    GitlabTooManyTokensException,
    GitlabEventListenerConflict,
    GitlabIllegalEventName,
)

event_handler = EventHandler()
system_event_handler = SystemEventHandler()


def validate_token_mapping(token_mapping: dict[str, list[str]]) -> None:
    if len(token_mapping.keys()) == 0:
        raise GitlabTokenNotFoundException(
            "There must be at least one token in tokenMapping"
        )


def validate_use_system_hook(token_mapping: dict[str, list[str]]) -> None:
    if len(token_mapping.keys()) > 1:
        raise GitlabTooManyTokensException()


def validate_hooks_tokens_are_in_token_mapping(
    token_mapping: dict[str, list[str]],
    token_group_override_hooks_mapping: dict[str, dict[str, dict[str, list[str]]]],
) -> None:
    for token in token_group_override_hooks_mapping:
        if token not in token_mapping:
            raise GitlabTokenNotFoundException(
                "Tokens from tokenGroupHooksOverrideMapping should also be in tokenMapping"
            )


def isHeirarchal(group_path: str, second_group_path: str) -> bool:
    return (
        second_group_path.startswith(group_path)
        and second_group_path[len(group_path)] == "/"
    )


def validate_unique_groups_paths(groups: dict[str, dict[str, list[str]]]) -> None:
    for group_path in groups:
        for second_group_path in groups:
            if second_group_path != group_path and isHeirarchal(
                group_path, second_group_path
            ):
                raise GitlabEventListenerConflict(
                    "Cannot listen to multiple groups with hierarchy to one another."
                    f" Group: {second_group_path} is inside group: {group_path}"
                )


def validate_groups_hooks_events(groups: dict[str, dict[str, list[str]]]) -> None:
    valid_events_names = GitlabService.all_events_in_webhook
    for group_path, values in groups.items():
        for event_name in values.get("events", []):
            if event_name not in valid_events_names:
                raise GitlabIllegalEventName(
                    f"Configured illegal event name: '{event_name}' "
                    f"in tokenGroupHooksOverrideMapping group: {group_path}. "
                    f"valid events are: {valid_events_names}"
                )


def validate_hooks_override_config(
    token_mapping: dict[str, list[str]],
    token_group_override_hooks_mapping: dict[str, dict[str, dict[str, list[str]]]],
) -> None:
    if not token_group_override_hooks_mapping:
        return

    validate_hooks_tokens_are_in_token_mapping(
        token_mapping, token_group_override_hooks_mapping
    )
    groups_paths: dict[str, dict[str, list[str]]] = merge_all_groups(
        token_group_override_hooks_mapping
    )
    validate_unique_groups_paths(groups_paths)
    validate_groups_hooks_events(groups_paths)


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


def create_webhooks_by_client(
    gitlab_host: str,
    app_host: str,
    token: str,
    groups_hooks_events_override: dict[str, dict[str, list[str]]] | None,
    group_mapping: list[str],
) -> tuple[GitlabService, list[int | str]]:
    gitlab_client = Gitlab(gitlab_host, token)
    gitlab_service = GitlabService(gitlab_client, app_host, group_mapping)

    specified_groups: list[str] | None = None

    if groups_hooks_events_override is not None:
        specified_groups = list(groups_hooks_events_override.keys())

    groups_for_webhooks = gitlab_service.get_filtered_groups_for_webhooks(
        specified_groups
    )

    webhook_groups_ids: list[int | str] = []

    for group in groups_for_webhooks:
        group_events: list[str] | None = None

        if groups_hooks_events_override:
            group_events = groups_hooks_events_override.get(
                group.attributes["full_path"], {}
            ).get("events")

        webhook_group_id = gitlab_service.create_webhook(group, group_events)

        if webhook_group_id:
            webhook_groups_ids.append(webhook_group_id)

    return gitlab_service, webhook_groups_ids


def setup_application(
    token_mapping: dict[str, list[str]],
    gitlab_host: str,
    app_host: str,
    use_system_hook: bool,
    token_group_override_hooks_mapping: dict[str, dict[str, dict[str, list[str]]]],
) -> None:
    validate_token_mapping(token_mapping)

    if use_system_hook:
        validate_use_system_hook(token_mapping)
        token, group_mapping = list(token_mapping.items())[0]
        gitlab_client = Gitlab(gitlab_host, token)
        gitlab_service = GitlabService(gitlab_client, app_host, group_mapping)
        setup_system_listeners([gitlab_service])

    else:
        validate_hooks_override_config(
            token_mapping, token_group_override_hooks_mapping
        )

        client_to_webhooks: list[tuple[GitlabService, list[int | str]]] = []
        for token, group_mapping in token_mapping.items():
            groups_override_paths_to_events: dict[str, dict[str, list[str]]] | None = (
                token_group_override_hooks_mapping.get(token, {})
                if token_group_override_hooks_mapping
                else None
            )

            client_to_webhooks.append(
                create_webhooks_by_client(
                    gitlab_host,
                    app_host,
                    token,
                    groups_override_paths_to_events,
                    group_mapping,
                )
            )

        for client, webhook_ids in client_to_webhooks:
            for webhook_id in webhook_ids:
                setup_listeners(client, webhook_id)
