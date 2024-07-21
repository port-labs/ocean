import requests

JIT_BASE_API_URL = "https://api.cto.jitdev.io"
JIT_FINDINGS_URL = f"{JIT_BASE_API_URL}/findings"


def get_findings(bearer):
    headers = {"Authorization": f"Bearer {bearer}"}

    response = requests.get(JIT_FINDINGS_URL, headers=headers)

    return response.json()
