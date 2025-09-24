import asyncio
import os

from azure_devops.client.azure_devops_client import AzureDevopsClient


async def main():
    """
    Makes repeated requests to the Azure DevOps API to trigger throttling and inspect rate limit headers.
    """
    try:
        org_url = os.environ["AZURE_DEVOPS_ORGANIZATION_URL"]
        pat = os.environ["AZURE_DEVOPS_PERSONAL_ACCESS_TOKEN"]
    except KeyError as e:
        print(f"Error: Missing environment variable {e}")
        print(
            "Please set AZURE_DEVOPS_ORGANIZATION_URL and AZURE_DEVOPS_PERSONAL_ACCESS_TOKEN"
        )
        return

    client = AzureDevopsClient(organization_url=org_url, personal_access_token=pat)
    num_runs = 5  # Number of times to run the full repository fetch

    print(f"Fetching all repositories {num_runs} times to trigger rate limiting...")
    print("Your print statements in rate_limiter.py should now produce output.")

    for i in range(num_runs):
        print(f"--- Starting run #{i + 1}/{num_runs} ---")
        # Fully consume the generator to ensure all API calls are made
        repositories = [
            repo async for page in client.generate_repositories() for repo in page
        ]
        print(f"Run #{i + 1} finished. Fetched {len(repositories)} repositories.")
        # Clear cache between runs to force refetching
        client.cache.clear()

    print("Script finished.")


if __name__ == "__main__":
    asyncio.run(main())
