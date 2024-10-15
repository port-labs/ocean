import asyncio
import os

import aiohttp
import click

from port_ocean.cli.commands.main import cli_start, console


def download_github_folder(
        owner: str, repo_name: str, folder_path: str, destination_path: str
) -> None:
    # Construct the API URL to get the contents of the folder
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{folder_path}"

    # Send a GET request to the API
    response = asyncio.run(aiohttp.ClientSession().request("GET", api_url))

    # Check if the request was successful
    if response.is_error:
        text = asyncio.run(response.text())
        console.print(
            f"[bold red]Failed to download the folder `{folder_path}`.[/bold red] Status Code: {response.status}, Error: {text}"
        )
        exit(1)

    # Create the destination folder if it doesn't exist
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    async def read_async():
        async with aiohttp.ClientSession().request("GET", file_url) as file_response:
            if file_response.status == 200:
                with open(file_name, "wb") as file:
                    file.write(await file_response.read())
            else:
                text = asyncio.run(file_response.text())
                console.print(
                    f"[bold red]Failed to download file `{content['name']}`.[/bold red] Status code: {file_response.status}, Error: {text}"
                )
                exit(1)

    # Iterate over the files and download them
    repo_contents = await response.json()
    for content in repo_contents:
        if content["type"] == "file":
            file_url = content["download_url"]
            file_name = os.path.join(destination_path, content["name"])

            # Download the file
            asyncio.run(read_async())

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
