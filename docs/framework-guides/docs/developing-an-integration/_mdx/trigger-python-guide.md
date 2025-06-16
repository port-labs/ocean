```python showLineNumbers
import requests

integration_identifier = "YOUR_INTEGRATION_IDENTIFIER_HERE"
jwt_token = "YOUR_JWT_TOKEN_HERE"

url = f"https://api.getport.io/v1/integration/{integration_identifier}"

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Content-Type": "application/json"
}

response = requests.patch(url, headers=headers, json={})

```