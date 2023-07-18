import warnings
from importlib.metadata import version

warnings.filterwarnings("ignore", category=FutureWarning)

from .ocean import Ocean
from .run import run

__version__ = version("port-ocean")


__all__ = ["Ocean", "run"]
