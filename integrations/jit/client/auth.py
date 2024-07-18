import requests

JIT_BASE_API_URL = "https://api.cto.jitdev.io"
JIT_AUTH_URL = f"{JIT_BASE_API_URL}/authentication/login"


def get_jwt_token(clientId, secret):
    payload = {"clientId": clientId, "secret": secret}
    headers = {"accept": "application/json", "content-type": "application/json"}

    response = requests.post(JIT_AUTH_URL, json=payload, headers=headers)

    return response.json()["accessToken"]
