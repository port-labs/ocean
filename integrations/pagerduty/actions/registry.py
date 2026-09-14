from port_ocean.context.ocean import ocean

from actions.acknowledge_incident_executor import AcknowledgeIncidentExecutor
from actions.resolve_incident_executor import ResolveIncidentExecutor
from actions.trigger_incident_executor import TriggerIncidentExecutor


def register_action_executors() -> None:
    """Register all action executors."""
    ocean.register_action_executor(TriggerIncidentExecutor())
    ocean.register_action_executor(AcknowledgeIncidentExecutor())
    ocean.register_action_executor(ResolveIncidentExecutor())
