import os
from dotenv import load_dotenv
from types import SimpleNamespace

# Load environment variables
load_dotenv()

class ConfigWrapper(SimpleNamespace):
    def __init__(self):
        config = SimpleNamespace(
            integration=SimpleNamespace(
                identifier="bitbucket",
                bitbucket=SimpleNamespace(
                    workspace=os.getenv("BITBUCKET_WORKSPACE"),
                    username=os.getenv("BITBUCKET_USERNAME"),
                    app_password=os.getenv("BITBUCKET_APP_PASSWORD")
                )
            )
        )
        super().__init__(**vars(config))
        self.config = self  
        self.context = self  

CONFIG = ConfigWrapper()
