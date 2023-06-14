import requests


def list_git_folders(repo_url: str, path: str) -> list[str]:
    # Parse the repository URL to extract the owner and repository name
    parts = repo_url.split("/")
    owner = parts[-2]
    repo_name = parts[-1].split(".")[0]

    # Construct the API URL to get the contents of the folder
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"

    # Send a GET request to the API
    response = requests.get(api_url)

    # Check if the request was successful
    if response.status_code == 200:
        contents = response.json()
        folders = [item["name"] for item in contents if item["type"] == "dir"]
        return folders
    else:
        print(f"Failed to list folders. {response.text}")
        return []
