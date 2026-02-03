from typing import Optional

from .basic_authenticator import HarborBasicAuthenticator
from .robot_authenticator import HarborRobotAuthenticator
from loguru import logger
from harbor.helpers.exceptions import MissingCredentials, MissingConfiguration


class HarborAuthenticatorFactory:
    """Factory for creating Harbor authenticators based on configuration"""

    @staticmethod
    def create(
        harbor_host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        robot_name: Optional[str] = None,
        robot_token: Optional[str] = None,
    ) -> HarborBasicAuthenticator | HarborRobotAuthenticator:
        # Validate required configuration
        if not harbor_host:
            raise MissingConfiguration("harbor_host is required in configuration")

        # Prefer robot account authentication (recommended for automation)
        if robot_name and robot_token:
            logger.debug(
                f"Creating Robot Account Authenticator for {robot_name} on Harbor"
            )
            return HarborRobotAuthenticator(robot_name, robot_token)

        # Fall back to user authentication
        if username and password:
            logger.debug(f"Creating Basic Authenticator for {username} on Harbor")
            return HarborBasicAuthenticator(username, password)

        raise MissingCredentials(
            "No valid Harbor credentials provided. "
            "Please provide either (robot_name, robot_token) for robot account authentication "
            "or (username, password) for user authentication."
        )
