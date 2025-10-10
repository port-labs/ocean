"""Debug entry point for the HTTP Server integration.

This file is used by VS Code launch configurations to run the integration
with debugging support.
"""

from port_ocean import run

if __name__ == "__main__":
    # The run() function will automatically import main.py and register handlers
    run()
