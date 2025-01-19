from port_ocean.exceptions.base import BaseOceanException


class AbortDefaultCreationError(BaseOceanException):
    def __init__(
        self,
        blueprints_to_rollback: list[str],
        errors: list[Exception],
    ):
        self.blueprints_to_rollback = blueprints_to_rollback
        self.errors = errors
        super().__init__("Aborting defaults creation")


class UnsupportedDefaultFileType(BaseOceanException):
    pass


class DefaultsProvisionFailed(BaseOceanException):
    def __init__(
        self,
        retries: int,
    ):
        super().__init__(
            f"Failed to retrieve integration config after {retries} attempts"
        )
