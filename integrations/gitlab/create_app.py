from typing import List, Dict

from pydantic import BaseSettings, AnyHttpUrl, Field
from pydantic.tools import parse_obj_as

from gitlab_integration.integration import GitlabIntegration
from port_ocean.ocean import Ocean


class LogicSettings(BaseSettings):
    token_mapping: Dict[str, List[str]] = Field(alias="tokenMapping")
    app_host: AnyHttpUrl = Field(alias="appHost")
    gitlab_host: AnyHttpUrl = Field(
        alias="gitlabHost", default=parse_obj_as(AnyHttpUrl, "https://gitlab.com")
    )


def create_app() -> Ocean:
    app = Ocean(integration_class=GitlabIntegration, config_factory=LogicSettings)
    # noinspection PyUnresolvedReferences
    # ruff: noqa: F401
    from gitlab_integration import ocean

    return app
