from port_ocean import ocean
from jira.client import JiraClient


def setup_application() -> None:
    logic_settings = ocean.integration_config

    jira_client = JiraClient(
        logic_settings.get("jira_host"),
        logic_settings.get("atlassian_user_email"),
        logic_settings.get("atlassian_user_token"),
    )

    jira_client.create_rt_issue_updates_webhook(
        logic_settings.get("app_host"),
    )
