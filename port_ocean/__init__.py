try:
    import click
    import cookiecutter  # type: ignore
    import rich

    cli_included = True
except ImportError:
    cli_included = False

defaults = [
    "clients",
    "config",
    "consumers",
    "context",
    "core",
    "models",
    "logging",
    "port_ocean",
]

if cli_included:
    from port_ocean.cli import cli

    __all__ = [*defaults, "cli"]
else:
    __all__ = defaults
