from typing import Any

from gunicorn.app.base import BaseApplication


class GunicornApplication(BaseApplication):
    def __init__(self, app: Any, options: dict[str, Any] | None = None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self) -> None:
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self) -> Any:
        return self.application
