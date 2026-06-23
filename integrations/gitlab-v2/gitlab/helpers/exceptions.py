from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""


class GitlabTriggerPipelineError(ActionExecutionError):
    """Raised when the GitLab API returns an error while triggering a pipeline."""
