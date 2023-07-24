from importlib.util import find_spec

try:
    find_spec("click")
    find_spec("rich")
    find_spec("cookiecutter")
    find_spec("jinja2-time")

    cli_included = True
except ImportError:
    raise ImportError(
        "The CLI is not available. Please install the CLI dependencies using: pip install port-ocean[cli]"
    )
