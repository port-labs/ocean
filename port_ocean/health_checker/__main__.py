"""Entry point for running the health checker as a sidecar: python -m port_ocean.health_checker"""

from port_ocean.health_checker.run import run_health_checker

if __name__ == "__main__":
    run_health_checker()
