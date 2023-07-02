from typing import List, Dict

from pydantic import BaseSettings, AnyHttpUrl, Field
from pydantic.tools import parse_obj_as

from gitlabapp.integration import GitlabIntegration
from port_ocean.logger_setup import setup_logger
from port_ocean.ocean import Ocean


class LogicSettings(BaseSettings):
    token_mapping: Dict[str, List[str]] = Field(alias="tokenMapping")
    app_host: AnyHttpUrl = Field(alias="appHost")
    gitlab_host: AnyHttpUrl = Field(
        alias="gitlabHost", default=parse_obj_as(AnyHttpUrl, "https://gitlab.com")
    )


def create_app() -> Ocean:
    setup_logger()
    app = Ocean(integration_class=GitlabIntegration, config_class=LogicSettings)
    # noinspection PyUnresolvedReferences
    from gitlabapp import ocean

    return app
