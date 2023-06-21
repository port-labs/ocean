from gitlab import Gitlab

from gitlabapp.events.event_handler import EventHandler
from gitlabapp.events.hooks.push import PushHook
from gitlabapp.services.gitlab_service import GitlabService
from port_ocean.context.integration import ocean


def setup_listeners(gitlab_service, webhook_id: str):
    event_handler = EventHandler()
    handlers = [PushHook(gitlab_service)]
    for handler in handlers:
        event_ids = [f"{event_name}:{webhook_id}" for event_name in handler.events]
        event_handler.on(event_ids, handler.on_hook)


def setup_application():
    logic_settings = ocean.integration_config
    for token, group_mapping in logic_settings["token_mapping"].items():
        gitlab_client = Gitlab(logic_settings["gitlab_host"], token)
        gitlab_service = GitlabService(
            gitlab_client, logic_settings["app_host"], group_mapping
        )
        webhook_ids = gitlab_service.create_webhooks()
        for webhook_id in webhook_ids:
            setup_listeners(gitlab_service, webhook_id)
