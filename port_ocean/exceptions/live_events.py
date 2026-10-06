from port_ocean.exceptions.base import BaseOceanException


class LiveEventsStreamKeyError(BaseOceanException):
    """Base exception for live events stream key resolution errors."""


class MissingLiveEventsBaseUrlError(LiveEventsStreamKeyError):
    def __init__(self) -> None:
        super().__init__(
            "base_url is required to resolve the Redis live events stream key"
        )


class LiveEventsUuidNotFoundError(LiveEventsStreamKeyError):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        super().__init__(
            "base_url must include /live-events/{uuid} "
            f"(e.g. https://host/live-events/your-uuid). Got: {base_url!r}"
        )


class LiveEventsRedisStreamError(BaseOceanException):
    """Base exception for Redis live events stream consumption errors."""


class InvalidLiveEventsRedisStreamFieldError(LiveEventsRedisStreamError):
    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Redis stream {field_name} field must contain a JSON object")
