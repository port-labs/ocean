try:
    from .commands import cli_start
except ImportError:
    print("Failed to import commands.")
