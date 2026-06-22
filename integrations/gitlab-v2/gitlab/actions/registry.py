from port_ocean.context.ocean import ocean

from gitlab.actions.trigger_pipeline_executor import TriggerPipelineExecutor


def register_actions_executors() -> None:
    ocean.register_action_executor(TriggerPipelineExecutor())
