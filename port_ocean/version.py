from importlib.metadata import version

from .utils.misc import get_integration_version

__version__ = version("port-ocean")
__integration_version__ = get_integration_version()
