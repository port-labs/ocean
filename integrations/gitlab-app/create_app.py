from typing import List, Dict

from gitlabapp.integration import GitlabIntegration
from port_ocean.port_ocean import Ocean
from pydantic import BaseSettings, AnyHttpUrl, Field


class LogicSettings(BaseSettings):
    token_mapping: Dict[str, List[str]] = Field(alias="tokenMapping")
    app_host: AnyHttpUrl = Field(alias="appHost")
    gitlab_host: AnyHttpUrl = Field(alias="gitlabHost", default="https://gitlab.com")

    class Config(BaseSettings.Config):
        env_prefix = "LOGIC_"


def create_app():
    app = Ocean(integration_class=GitlabIntegration, config_class=LogicSettings)
    # noinspection PyUnresolvedReferences
    from gitlabapp import ocean

    return app
