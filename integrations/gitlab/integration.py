from gitlab_integration.git_integration import GitlabPortAppConfig
from gitlab_integration.raw_enricher import GitlabRawEnricher
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class GitlabIntegration(BaseIntegration):
    RawEnricherClass = GitlabRawEnricher

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
