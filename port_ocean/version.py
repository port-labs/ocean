from importlib.metadata import version

from .utils import get_integration_version

__version__ = version("port-ocean")
__integration_version__ = get_integration_version()
