import requests
import os
import shutil


def download_folder(repo_url: str, folder_path: str, destination_path: str) -> None:
    # Parse the repository URL to extract the owner and repository name
    parts = repo_url.split("/")
    owner = parts[-2]
    repo_name = parts[-1].split(".")[0]

    # Construct the API URL to get the contents of the folder
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{folder_path}"

    # Send a GET request to the API
    response = requests.get(api_url)

    # Check if the request was successful
    if response.status_code == 200:
        # Create the destination folder if it doesn't exist
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        # Iterate over the files and download them
        files = response.json()
        for file in files:
            if file["type"] == "file":
                file_url = file["download_url"]
                file_name = os.path.join(destination_path, file["name"])

                # Download the file
                with requests.get(file_url, stream=True) as r:
                    with open(file_name, "wb") as f:
                        shutil.copyfileobj(r.raw, f)

        print("Folder downloaded successfully!")
    else:
        print("Failed to download the folder.")
