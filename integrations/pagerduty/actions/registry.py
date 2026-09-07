from port_ocean.context.ocean import ocean

from actions.trigger_incident_executor import TriggerIncidentExecutor


def register_action_executors() -> None:
    """Register all action executors."""
    ocean.register_action_executor(TriggerIncidentExecutor())
