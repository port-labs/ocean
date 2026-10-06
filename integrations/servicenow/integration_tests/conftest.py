import os
import sys

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Make the integration root importable so the harness can load main.py and its
# sibling modules (client, initialize_client, integration, auth, ...).
if INTEGRATION_PATH not in sys.path:
    sys.path.insert(0, INTEGRATION_PATH)
