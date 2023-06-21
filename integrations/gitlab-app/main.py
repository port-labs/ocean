from typing import List, Dict

import uvicorn
from gitlabapp.integration import GitlabIntegration
from port_ocean.port_ocean import Ocean
from pydantic import BaseSettings, AnyHttpUrl, Field


class LogicSettings(BaseSettings):
    token_mapping: Dict[str, List[str]] = Field(alias="tokenMapping")
    app_host: AnyHttpUrl = Field(alias="appHost")
    gitlab_host: AnyHttpUrl = Field(alias="gitlabHost")

    class Config(BaseSettings.Config):
        env_prefix = "LOGIC_"


if __name__ == "__main__":
    app = Ocean(integration_class=GitlabIntegration, config_class=LogicSettings)
    from gitlabapp import ocean

    uvicorn.run(app, host="0.0.0.0", port=8000)
