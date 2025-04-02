class GitHubHeaders(dict):
    """A dictionary subclass for building GitHub API headers using method chaining."""

    def add_authentication_header(self, token: str) -> 'GitHubHeaders':
        """Adds the Authentication header."""
        self['Authorization'] = f'token {token}'
        return self

    def add_accept_header(self) -> 'GitHubHeaders':
        """Adds the Accept header."""
        self['Accept'] = 'application/vnd.github+json'
        return self

    def add_api_version_header(self) -> 'GitHubHeaders':
        """Adds the X-GitHub-Api-Version header."""
        self['X-GitHub-Api-Version'] = '2022-11-28'
        return self

def get_github_base_headers(token: str) -> dict:
    """
    Returns a dictionary of base headers for GitHub API requests using the provided token.
    """
    return GitHubHeaders().add_api_version_header().add_accept_header().add_authentication_header(token)
