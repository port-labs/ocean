from .basic_authenticator import HarborBasicAuthenticator


class HarborRobotAuthenticator(HarborBasicAuthenticator):
    """Harbor Robot Authentication using robotName and robotToken"""

    def __init__(self, robot_name: str, robot_token: str):
        super().__init__(robot_name, robot_token)
