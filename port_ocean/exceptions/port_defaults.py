from port_ocean.exceptions.base import BaseOceanException


class AbortDefaultCreationError(BaseOceanException):
    def __init__(
        self,
        blueprints_to_rollback: list[str],
        errors: list[Exception],
        pages_to_rollback: list[str] | None = None,
    ):
        self.blueprints_to_rollback = blueprints_to_rollback
        self.pages_to_rollback = pages_to_rollback
        self.errors = errors
        super().__init__("Aborting defaults creation")


class UnsupportedDefaultFileType(BaseOceanException):
    pass
