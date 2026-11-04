from port_ocean.context.ocean import ocean

from actions.create_agent_executor import CreateAgentExecutor
from actions.delete_agent_executor import DeleteAgentExecutor
from actions.delete_model_deployment_executor import DeleteModelDeploymentExecutor
from actions.deploy_model_deployment_executor import DeployModelDeploymentExecutor
from actions.invoke_agent_executor import InvokeAgentExecutor
from actions.invoke_model_executor import InvokeModelExecutor
from actions.update_agent_executor import UpdateAgentExecutor


def register_action_executors() -> None:
    ocean.register_action_executor(CreateAgentExecutor())
    ocean.register_action_executor(UpdateAgentExecutor())
    ocean.register_action_executor(DeleteAgentExecutor())
    ocean.register_action_executor(InvokeAgentExecutor())
    ocean.register_action_executor(InvokeModelExecutor())
    ocean.register_action_executor(DeployModelDeploymentExecutor())
    ocean.register_action_executor(DeleteModelDeploymentExecutor())
