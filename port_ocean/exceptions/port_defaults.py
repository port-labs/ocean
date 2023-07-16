class AbortDefaultCreationError(Exception):
    def __init__(self, blueprints_to_rollback: list[str], errors: list[Exception]):
        self.blueprints_to_rollback = blueprints_to_rollback
        self.errors = errors
        super().__init__("Aborting defaults creation")
