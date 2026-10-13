from port_ocean.context.ocean import ocean

from gitlab.actions.create_merge_request_comment_executor import (
    CreateMergeRequestCommentExecutor,
)
from gitlab.actions.create_merge_request_executor import CreateMergeRequestExecutor
from gitlab.actions.set_merge_request_comment_reaction_executor import (
    SetMergeRequestCommentReactionExecutor,
)
from gitlab.actions.trigger_pipeline_executor import TriggerPipelineExecutor
from gitlab.actions.update_merge_request_executor import UpdateMergeRequestExecutor


def register_actions_executors() -> None:
    ocean.register_action_executor(TriggerPipelineExecutor())
    ocean.register_action_executor(CreateMergeRequestExecutor())
    ocean.register_action_executor(UpdateMergeRequestExecutor())
    ocean.register_action_executor(CreateMergeRequestCommentExecutor())
    ocean.register_action_executor(SetMergeRequestCommentReactionExecutor())
