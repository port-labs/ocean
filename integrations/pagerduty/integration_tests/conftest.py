import os
import sys

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if INTEGRATION_PATH not in sys.path:
    sys.path.insert(0, INTEGRATION_PATH)
