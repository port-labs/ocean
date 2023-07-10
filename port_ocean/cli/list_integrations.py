import httpx
from rich.console import Console

console = Console()


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
