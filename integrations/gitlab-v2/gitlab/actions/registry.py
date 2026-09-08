from port_ocean.context.ocean import ocean

from gitlab.actions.trigger_pipeline_executor import TriggerPipelineExecutor
from gitlab.actions.update_merge_request_executor import UpdateMergeRequestExecutor


def register_actions_executors() -> None:
    ocean.register_action_executor(TriggerPipelineExecutor())
    ocean.register_action_executor(UpdateMergeRequestExecutor())
