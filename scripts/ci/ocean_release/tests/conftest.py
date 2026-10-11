import sys
from pathlib import Path

CI_DIR = Path(__file__).resolve().parents[2]
if str(CI_DIR) not in sys.path:
    sys.path.insert(0, str(CI_DIR))
