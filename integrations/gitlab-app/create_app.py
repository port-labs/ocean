from typing import List, Dict

from gitlabapp.integration import GitlabIntegration
from port_ocean.port_ocean import Ocean
from pydantic import BaseSettings, AnyHttpUrl, Field
from pydantic.tools import parse_obj_as


class LogicSettings(BaseSettings):
    token_mapping: Dict[str, List[str]] = Field(alias="tokenMapping")
    app_host: AnyHttpUrl = Field(alias="appHost")
    gitlab_host: AnyHttpUrl = Field(
        alias="gitlabHost", default=parse_obj_as(AnyHttpUrl, "https://gitlab.com")
    )

    class Config(BaseSettings.Config):
        env_prefix = "LOGIC_"


def create_app() -> Ocean:
    app = Ocean(integration_class=GitlabIntegration, config_factory=LogicSettings)
    # noinspection PyUnresolvedReferences
    from gitlabapp import ocean

    return app
