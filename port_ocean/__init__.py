import warnings
from importlib.metadata import version

from .ocean import Ocean
from .run import run

__version__ = version("port-ocean")

warnings.filterwarnings("ignore", category=FutureWarning)

__all__ = ["Ocean", "run"]
