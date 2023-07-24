import os
import shutil
from io import BytesIO

import click
import httpx

from port_ocean.cli.commands.main import cli_start, console


def download_github_folder(
    owner: str, repo_name: str, folder_path: str, destination_path: str
) -> None:
    # Construct the API URL to get the contents of the folder
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{folder_path}"

    # Send a GET request to the API
    response = httpx.get(api_url)

    # Check if the request was successful
    if response.is_error:
        console.print(
            f"[bold red]Failed to download the folder `{folder_path}`.[/bold red] Status Code: {response.status_code}, Error: {response.text}"
        )
        exit(1)

    # Create the destination folder if it doesn't exist
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    # Iterate over the files and download them
    repo_contents = response.json()
    for content in repo_contents:
        if content["type"] == "file":
            file_url = content["download_url"]
            file_name = os.path.join(destination_path, content["name"])

            # Download the file
            with httpx.stream("GET", file_url) as file_response:
                if file_response.status_code == 200:
                    with open(file_name, "wb") as file:
                        shutil.copyfileobj(BytesIO(file_response.content), file)
                else:
                    console.print(
                        f"[bold red]Failed to download file `{content['name']}`.[/bold red] Status code: {file_response.status_code}, Error: {file_response.text}"
                    )
                    exit(1)

    console.print(f"Folder `{folder_path}` downloaded successfully!")


@cli_start.command()
@click.argument("name", type=str)
@click.option(
    "-p",
    "--path",
    "path",
    default=None,
    type=click.Path(exists=True),
    help="Desired path to pull the integration to. defaults to ./NAME",
)
def pull(name: str, path: str) -> None:
    """
    Pull an integration bt the NAME from the list of available public integrations.

    NAME: Name of the integration to pull.
    """
    download_github_folder(
        "port-labs", "Port-Ocean", f"integrations/{name}", path or f"./{name}"
    )
