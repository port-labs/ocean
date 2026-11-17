from pathlib import Path

from port_ocean.exceptions.base import BaseOceanException


class RouteFileLoadError(BaseOceanException):
    """Raised when a mock route YAML file cannot be read or validated."""

    def __init__(self, path: Path | str, message: str) -> None:
        self.path = Path(path)
        self.message = message
        super().__init__(f"Invalid mock route file '{self.path}': {message}")
