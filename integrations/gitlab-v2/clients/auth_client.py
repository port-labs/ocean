class AuthClient:
    def __init__(self, token: str):
        self.token = token

    def get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
