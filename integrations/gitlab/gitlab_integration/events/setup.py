from typing import Type, List

from gitlab import Gitlab

from loguru import logger

from gitlab_integration.events.event_handler import EventHandler, SystemEventHandler
from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.events.hooks.issues import Issues
from gitlab_integration.events.hooks.jobs import Job
from gitlab_integration.events.hooks.merge_request import MergeRequest
from gitlab_integration.events.hooks.pipelines import Pipelines
from gitlab_integration.events.hooks.push import PushHook
from gitlab_integration.events.hooks.group import GroupHook
from gitlab_integration.events.hooks.project_files import ProjectFiles
from gitlab_integration.gitlab_service import GitlabService
from gitlab_integration.models.webhook_groups_override_config import (
    WebhookMappingConfig,
    WebhookGroupConfig,
    WebhookTokenConfig,
)
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
    token_group_override_hooks_mapping: WebhookMappingConfig,
) -> None:
    for token in token_group_override_hooks_mapping.tokens:
        if token not in token_mapping:
            raise GitlabTokenNotFoundException(
                "Tokens from tokenGroupHooksOverrideMapping should also be in tokenMapping"
            )


def isHeirarchal(group_path: str, second_group_path: str) -> bool:
    return (
        second_group_path.startswith(group_path)
        and second_group_path[len(group_path)] == "/"
    )


def validate_unique_groups_paths(groups: dict[str, WebhookGroupConfig]) -> None:
    for group_path in groups:
        for second_group_path in groups:
            if second_group_path != group_path and isHeirarchal(
                group_path, second_group_path
            ):
                raise GitlabEventListenerConflict(
                    "Cannot listen to multiple groups with hierarchy to one another."
                    f" Group: {second_group_path} is inside group: {group_path}"
                )


def validate_groups_hooks_events(groups: dict[str, WebhookGroupConfig]) -> None:
    valid_events_names = GitlabService.all_events_in_webhook
    for group_path, webhook_group in groups.items():
        for event_name in webhook_group.events:
            if event_name not in valid_events_names:
                raise GitlabIllegalEventName(
                    f"Configured illegal event name: '{event_name}' "
                    f"in tokenGroupHooksOverrideMapping group: {group_path}. "
                    f"valid events are: {valid_events_names}"
                )


def extract_all_groups_from_token_group_override_mapping(
    token_group_override_hooks_mapping: WebhookMappingConfig,
) -> dict[str, WebhookGroupConfig]:
    all_groups: dict[str, WebhookGroupConfig] = {}

    for webhook_token_obj in token_group_override_hooks_mapping.tokens.values():
        all_groups.update(webhook_token_obj.groups)

    return all_groups


def validate_hooks_override_config(
    token_mapping: dict[str, list[str]],
    token_group_override_hooks_mapping: WebhookMappingConfig | None,
) -> None:
    if not token_group_override_hooks_mapping:
        return

    validate_hooks_tokens_are_in_token_mapping(
        token_mapping, token_group_override_hooks_mapping
    )
    groups_paths: dict[str, WebhookGroupConfig] = (
        extract_all_groups_from_token_group_override_mapping(
            token_group_override_hooks_mapping
        )
    )

    validate_unique_groups_paths(groups_paths)
    validate_groups_hooks_events(groups_paths)


def setup_listeners(gitlab_service: GitlabService, group_id: str) -> None:
    handlers = [
        PushHook(gitlab_service),
        MergeRequest(gitlab_service),
        Job(gitlab_service),
        Issues(gitlab_service),
        Pipelines(gitlab_service),
        GroupHook(gitlab_service),
        ProjectFiles(gitlab_service),
    ]
    for handler in handlers:
        logger.info(
            f"Setting up listeners {handler.events} for group {group_id} for group mapping {gitlab_service.group_mapping}"
        )
        event_ids = [f"{event_name}:{group_id}" for event_name in handler.events]
        event_handler.on(event_ids, handler.on_hook)


def setup_system_listeners(gitlab_clients: list[GitlabService]) -> None:
    handlers: List[Type[HookHandler]] = [
        PushHook,
        MergeRequest,
        Job,
        Issues,
        Pipelines,
        GroupHook,
        ProjectFiles,
    ]
    for handler in handlers:
        logger.info(f"Setting up system listeners {handler.system_events}")
        system_event_handler.on(handler)

    for gitlab_service in gitlab_clients:
        system_event_handler.add_client(gitlab_service)


async def create_webhooks_by_client(
    gitlab_host: str,
    app_host: str,
    token: str,
    groups_hooks_events_override: dict[str, WebhookGroupConfig] | None,
    group_mapping: list[str],
) -> tuple[GitlabService, list[str]]:
    gitlab_client = Gitlab(gitlab_host, token)
    gitlab_service = GitlabService(gitlab_client, app_host, group_mapping)

    groups_for_webhooks = await gitlab_service.get_filtered_groups_for_webhooks(
        list(groups_hooks_events_override.keys())
        if groups_hooks_events_override
        else None
    )

    groups_ids_with_webhooks: list[str] = []

    for group in groups_for_webhooks:
        group_id = await gitlab_service.create_webhook(
            group,
            (
                groups_hooks_events_override.get(
                    group.attributes["full_path"], WebhookGroupConfig(events=[])
                ).events
                if groups_hooks_events_override
                else None
            ),
        )

        if group_id:
            groups_ids_with_webhooks.append(group_id)

    return gitlab_service, groups_ids_with_webhooks


async def setup_application(
    token_mapping: dict[str, list[str]],
    gitlab_host: str,
    app_host: str,
    use_system_hook: bool,
    token_group_override_hooks_mapping: WebhookMappingConfig | None,
) -> None:
    validate_token_mapping(token_mapping)

    if use_system_hook:
        logger.info("Using system hook")
        validate_use_system_hook(token_mapping)
        token, group_mapping = list(token_mapping.items())[0]
        gitlab_client = Gitlab(gitlab_host, token)
        gitlab_service = GitlabService(gitlab_client, app_host, group_mapping)
        setup_system_listeners([gitlab_service])

    else:
        logger.info("Using group hooks")
        validate_hooks_override_config(
            token_mapping, token_group_override_hooks_mapping
        )

        client_to_group_ids_with_webhooks: list[tuple[GitlabService, list[str]]] = []

        for token, group_mapping in token_mapping.items():
            try:
                if not token_group_override_hooks_mapping:
                    client_to_group_ids_with_webhooks.append(
                        await create_webhooks_by_client(
                            gitlab_host,
                            app_host,
                            token,
                            None,
                            group_mapping,
                        )
                    )
                else:
                    groups = token_group_override_hooks_mapping.tokens.get(
                        token, WebhookTokenConfig(groups=[])
                    ).groups
                    if groups:
                        client_to_group_ids_with_webhooks.append(
                            await create_webhooks_by_client(
                                gitlab_host,
                                app_host,
                                token,
                                groups,
                                group_mapping,
                            )
                        )
            except Exception as e:
                logger.exception(
                    f"Failed to create webhooks for group mapping {group_mapping}, error: {e}"
                )

        for client, group_ids in client_to_group_ids_with_webhooks:
            for group_id in group_ids:
                setup_listeners(client, group_id)
