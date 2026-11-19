from pathlib import Path


class RouteFileLoadError(Exception):
    """Raised when a mock route YAML file cannot be read or validated."""

    def __init__(self, path: Path | str, message: str) -> None:
        self.path = Path(path)
        self.message = message
        super().__init__(f"Invalid mock route file '{self.path}': {message}")
