# -*- coding: utf-8 -*-
import httpx

from port_ocean.cli.commands.main import cli_start, console


def list_git_folders(owner: str, repo_name: str, path: str) -> list[str]:
    # Construct the API URL to get the contents of the folder
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"

    # Send a GET request to the API
    response = httpx.get(api_url)

    # Check if the request was successful
    if response.is_error:
        console.print(
            f"[bold red]Failed to list folders.[/bold red] Status Code: {response.status_code}, Error: {response.text}"
        )
        exit(1)

    contents = response.json()
    folders = [item["name"] for item in contents if item["type"] == "dir"]
    return folders


@cli_start.command(name="list")
def list_integrations() -> None:
    """
    List all available public integrations.
    """
    console.print("🌊 Here are the integrations available to you:", style="bold")
    options = list_git_folders("port-labs", "port-ocean", "integrations")

    for option in options:
        console.print(f"⚓️ [bold][blue]{option}[/blue][/bold]")
