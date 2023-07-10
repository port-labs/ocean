import warnings
from importlib.metadata import version
from importlib.util import find_spec

__version__ = version("port-ocean")

warnings.filterwarnings("ignore", category=FutureWarning)


try:
    find_spec("click")
    find_spec("cookiecutter")
    find_spec("rich")
    find_spec("toml")

    cli_included = True
except ImportError:
    cli_included = False

defaults = [
    "clients",
    "config",
    "consumers",
    "context",
    "core",
    "common",
    "logging",
    "port_ocean",
]

if cli_included:
    from port_ocean.cli import cli

    __all__ = [*defaults, "cli"]
else:
    __all__ = defaults
