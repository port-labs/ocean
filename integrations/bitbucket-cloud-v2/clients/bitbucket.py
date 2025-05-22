from loguru import logger


class BitbucketClient:
    def __init__(self, username: str, password: str, workspace: str):
        logger.info("Initializing BitBucket Client")
        self.username = username
        self.password = password
        self.workspace = workspace
