# -*- coding: utf-8 -*-

import json
import os

import click
from cookiecutter.main import cookiecutter  # type: ignore

from port_ocean.cli.commands.main import cli_start, console, print_logo
from port_ocean.cli.utils import cli_root_path


def add_vscode_configuration(result: str, name: str) -> None:
    vscode_entry_root_path = "${workspaceFolder}/integrations/" + name
    new_vscode_entry = {
        "console": "integratedTerminal",
        "cwd": vscode_entry_root_path,
        "envFile": f"{vscode_entry_root_path}/.env",
        "justMyCode": True,
        "name": f"Run {name} integration",
        "program": f"{vscode_entry_root_path}/debug.py",
        "python": f"{vscode_entry_root_path}/.venv/bin/python",
        "request": "launch",
        "type": "debugpy",
    }

    vs_code_json_path = os.path.join(os.path.dirname(result), "../.vscode/launch.json")
    if not os.path.exists(vs_code_json_path):
        return
    vs_code_json = json.load(open(vs_code_json_path, "r"))
    vs_code_json["configurations"].append(new_vscode_entry)

    with open(vs_code_json_path, "w") as vs_code_json_file:
        json.dump(vs_code_json, vs_code_json_file, indent=2)
        vs_code_json_file.write("\n")


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--private/--public",
    "is_private_integration",
    is_flag=True,
    default=True,
    help="Handle private integrations scaffolding. (Used for contributing to Ocean when set to public)",
)
def new(path: str, is_private_integration: bool) -> None:
    """
    Scaffold a new integration in the given PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    print_logo()

    console.print(
        "🚢 Unloading cargo... Setting up your integration at the dock.", style="bold"
    )

    result = cookiecutter(
        f"{cli_root_path}/cookiecutter",
        output_dir=path,
        extra_context={
            "is_private_integration": is_private_integration,
        },
    )

    name = result.split("/")[-1]

    final_private_integration = os.path.exists(os.path.join(result, "Dockerfile"))

    if not final_private_integration:
        add_vscode_configuration(result, name)

    console.print(
        "\n🌊 Ahoy, Captain! Your project is ready to set sail into the vast ocean of possibilities!",
        style="bold",
    )
    console.print("Here are your next steps:\n", style="bold")
    console.print(
        f"⚓️ Install necessary packages: Run [bold][blue]cd {path}/{name} && make install && . .venv/bin/activate[/blue][/bold] to install all required packages for your project."
    )
    console.print(
        "⚓️ Copy example env file: Run [bold][blue]cp .env.example .env [/blue][/bold] and update your integration's configuration in the .env file."
    )
    console.print(
        "⚓️ Set sail with [blue]Ocean[/blue]: Run [bold][blue]ocean sail[/blue][/bold] to run the project using Ocean."
    )
    if not final_private_integration:
        console.print(
            f"⚓️ Smooth sailing with [blue]Make[/blue]: Alternatively, you can run [bold][blue]make run {path}/{name}[/blue][/bold] to launch your project using Make."
        )
