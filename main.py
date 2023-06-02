import argparse

import yaml

from framework.core.integrations_orchestrator.integrations_orchestrator import IntegrationsOrchestrator

if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--integrations-config', type=str)

    # Parse the command-line arguments
    args = parser.parse_args()

    # Extract the value of the 'integrations-config' argument
    integrations_config_path = args.integrations_config

    # Load the integrations config file from yaml to dict
    with open(integrations_config_path, 'r') as stream:
        integrations_config = yaml.safe_load(stream)

    # Create an integrations orchestrator for the given integration config
    integrations_orchestrator = IntegrationsOrchestrator(
        integrations_config=integrations_config
    )