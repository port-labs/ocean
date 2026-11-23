from port_ocean.context.ocean import ocean

from azure_integration.foundry.actions.create_agent_executor import CreateAgentExecutor
from azure_integration.foundry.actions.delete_agent_executor import DeleteAgentExecutor
from azure_integration.foundry.actions.delete_model_deployment_executor import (
    DeleteModelDeploymentExecutor,
)
from azure_integration.foundry.actions.deploy_model_deployment_executor import (
    DeployModelDeploymentExecutor,
)
from azure_integration.foundry.actions.invoke_agent_executor import InvokeAgentExecutor
from azure_integration.foundry.actions.invoke_model_executor import InvokeModelExecutor
from azure_integration.foundry.actions.update_agent_executor import UpdateAgentExecutor


def register_action_executors() -> None:
    ocean.register_action_executor(CreateAgentExecutor())
    ocean.register_action_executor(UpdateAgentExecutor())
    ocean.register_action_executor(DeleteAgentExecutor())
    ocean.register_action_executor(InvokeAgentExecutor())
    ocean.register_action_executor(InvokeModelExecutor())
    ocean.register_action_executor(DeployModelDeploymentExecutor())
    ocean.register_action_executor(DeleteModelDeploymentExecutor())
