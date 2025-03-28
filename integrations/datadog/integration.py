from enum import StrEnum
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from overrides import DataDogPortAppConfig


class ObjectKind(StrEnum):
    HOST = "host"
    MONITOR = "monitor"
    SLO = "slo"
    SERVICE = "service"
    SLO_HISTORY = "sloHistory"
    SERVICE_METRIC = "serviceMetric"
    TEAM = "team"
    USER = "user"


class DatadogIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
