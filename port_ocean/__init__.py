import warnings
from importlib.metadata import version

warnings.filterwarnings("ignore", category=FutureWarning)

from .ocean import Ocean  # noqa: E402
from .run import run  # noqa: E402

__version__ = version("port-ocean")


__all__ = ["Ocean", "run", "__version__"]
