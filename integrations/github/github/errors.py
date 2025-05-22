import typing as t


class WebhookSignatureError(Exception):
    pass


class MissingHeaderError(Exception):
    pass


class GithubError(Exception):
    def __init__(
        self,
        message: str,
        status_code: t.Optional[int] = None,
        response_data: t.Optional[t.Any] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class GithubRateLimitError(GithubError):
    def __init__(self, message: str, reset_time: t.Optional[int] = None):
        super().__init__(message)
        self.reset_time = reset_time


class GithubNotFoundError(GithubError):
    pass


class GithubAPIError(GithubError):
    pass
