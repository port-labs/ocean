from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from azure_devops.gitops.file_entity_processor import GitManipulationHandler
from azure_devops.misc import GitPortAppConfig


class AzureDevopsIntegration(BaseIntegration):
    EntityProcessorClass = GitManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitPortAppConfig
