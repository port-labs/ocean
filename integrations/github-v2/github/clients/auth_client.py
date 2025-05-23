class AuthClient:
    def __init__(self, token: str):
        """
        Initialize GitHub authentication client.

        Args:
            token: GitHub personal access token or OAuth token
        """
        self.token = token

    def get_headers(self) -> dict[str, str]:
        """
        Get the authentication headers for GitHub API requests.

        Returns:
            Dictionary with authorization headers
        """
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }
