class MissingExecutionPropertyError(Exception):
    """Raised when a required execution property is absent from the action run."""


class GitlabTriggerPipelineError(Exception):
    """Raised when the GitLab API returns an error while triggering a pipeline."""
