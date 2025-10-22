import base64
from typing import Optional

def generate_basic_auth_header(username: str, password: str) -> tuple[str, str]:
    """
    Returns the Basic Auth header for given username and password
    """
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    return 'Authorization', f'Basic {encoded}'
