try:
    from .commands import cli_start  # ruff: noqa: F401
except ImportError:
    print("Failed to import commands.")
