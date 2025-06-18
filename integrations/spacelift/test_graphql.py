import requests

SPACELIFT_BEARER_TOKEN = "eyJhbGciOiJLTVMiLCJ0eXAiOiJKV1QifQ.eyJhdWQiOlsiaHR0cHM6Ly9wb3J0amF5LmFwcC5zcGFjZWxpZnQuaW8iXSwiZXhwIjoxNzUwMjc4MzczLjA4NjQxMSwianRpIjoiMDFKWTE5NkJFWTVLOVFUMFY4WFFYRkpSQUUiLCJpYXQiOjE3NTAyNDIzNzMuMDg2NDExLCJpc3MiOiJhcGkta2V5IiwibmJmIjoxNzUwMjQyMzczLjA4NjQxMiwic3ViIjoiYXBpOjowMUpZMTdGRkE2ODczNVJWMFoxS05YTkVOOCIsImFkbSI6dHJ1ZSwiYXZ0IjoiaHR0cHM6Ly93d3cuZ3JhdmF0YXIuY29tL2F2YXRhci80ZTcyZDljNGM3ZjE1ZDgzMzYxM2JmMmU1ZDdiZWM0Ny5qcGc_ZD1yb2JvaGFzaFx1MDAyNnNpemU9ODAiLCJjaXAiOiIxMDMuMjQxLjIzMi4yMDAiLCJwc2EiOiIwMUpZMTk2QkZQRFM4VzBUQUQ3MUhQUFMxUSIsIklzTWFjaGluZVVzZXIiOmZhbHNlLCJJc0ludGVncmF0aW9uIjpmYWxzZSwic3ViZG9tYWluIjoicG9ydGpheSIsImZ1bGxfbmFtZSI6InBvcnQgaW50ZWdyYXRpb24ifQ.Ptk4ru+MMRBT168S/xI+4AjlsR4nrQ7RiSM3sLah+7W2/4q4Oc/Jtt/XIJderSETADiyKQV24E+m7ssAXBcD8vNGyM0TS1Be38vkjy4JkCVHUptcJytNPzxxHLxw3geCO7BNcKDTLFRH0dkkBvAawRV3x4EKPGShP13fGIVAYHWHtvy2pBJPkUMO5/uwxtDx5ricRrHoPWiE/Tn7ir0CsKippSQC260WY+0Hz/14Wy92VH5P2NrqaU7FgoFR8i2Idlj2vGn/uir+MOFnbEXSB15o1hzTGDwclBomXVI7cKCQgvw5yK3hS4hyFtXoI7ZUM3l3jxjA9y4E4/tH1fowcFS1OMitW/ccMcNuUVhLjJ7GDGW5KQe3esKEu7i/ydzUxjK2v+BOvGu0ta+69XaDVff64tgqM0bPnY4j1ITHKM51tMKyiWn+Lc583Xcn6X5YErK/+O/+BVUm3uznoye5wYpeerFm9D97rPO0YUmE7L9eo9FO7WMjBc0Aii6NSUV6t8gvFv/QIbidGlU8MzFXCH0Pw+ZDeHVHBilBcE9KExb7wsTK1m62/ljBraCkAXJAogC5uVW17o4nw4dNoogHLpiUGVRmT1Ykl1Nksw7iVqJx/vfSs+6Gkw5Y+FcZtAYcPEqF5pAn0ZcNxgeOon8sUK7C8Jsnsh5iI24DOotCo9M="

url = "https://portjay.app.spacelift.io/graphql"  # ✅ Your custom account URL

headers = {
    "Authorization": f"Bearer {SPACELIFT_BEARER_TOKEN}",
    "Content-Type": "application/json"
}

query = """
{
  stacks {
    id
    name
  }
}
"""

response = requests.post(url, json={"query": query}, headers=headers)

print("Status Code:", response.status_code)
print("Response:", response.json())


# import requests

# SPACELIFT_ACCOUNT = "portjay"  # e.g., "portjay"
# GRAPHQL_URL = f"https://{SPACELIFT_ACCOUNT}.app.spacelift.io/graphql"

# API_KEY_ID = "01JY17FFA68735RV0Z1KNXNEN8"
# API_KEY_SECRET = "db6e7a76314af1671da4061122d4f3afc56cbca9e0787d47581df36ce28a9c20"

# query = """
# mutation GetSpaceliftToken($id: ID!, $secret: String!) {
#   apiKeyUser(id: $id, secret: $secret) {
#     jwt
#   }
# }
# """

# variables = {
#     "id": API_KEY_ID,
#     "secret": API_KEY_SECRET
# }

# headers = {"Content-Type": "application/json"}

# response = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables}, headers=headers)

# data = response.json()
# print("JWT:", data)


# JWT: {'data': {'apiKeyUser': {'jwt': 'eyJhbGciOiJLTVMiLCJ0eXAiOiJKV1QifQ.eyJhdWQiOlsiaHR0cHM6Ly9wb3J0amF5LmFwcC5zcGFjZWxpZnQuaW8iXSwiZXhwIjoxNzUwMjc4MzczLjA4NjQxMSwianRpIjoiMDFKWTE5NkJFWTVLOVFUMFY4WFFYRkpSQUUiLCJpYXQiOjE3NTAyNDIzNzMuMDg2NDExLCJpc3MiOiJhcGkta2V5IiwibmJmIjoxNzUwMjQyMzczLjA4NjQxMiwic3ViIjoiYXBpOjowMUpZMTdGRkE2ODczNVJWMFoxS05YTkVOOCIsImFkbSI6dHJ1ZSwiYXZ0IjoiaHR0cHM6Ly93d3cuZ3JhdmF0YXIuY29tL2F2YXRhci80ZTcyZDljNGM3ZjE1ZDgzMzYxM2JmMmU1ZDdiZWM0Ny5qcGc_ZD1yb2JvaGFzaFx1MDAyNnNpemU9ODAiLCJjaXAiOiIxMDMuMjQxLjIzMi4yMDAiLCJwc2EiOiIwMUpZMTk2QkZQRFM4VzBUQUQ3MUhQUFMxUSIsIklzTWFjaGluZVVzZXIiOmZhbHNlLCJJc0ludGVncmF0aW9uIjpmYWxzZSwic3ViZG9tYWluIjoicG9ydGpheSIsImZ1bGxfbmFtZSI6InBvcnQgaW50ZWdyYXRpb24ifQ.Ptk4ru+MMRBT168S/xI+4AjlsR4nrQ7RiSM3sLah+7W2/4q4Oc/Jtt/XIJderSETADiyKQV24E+m7ssAXBcD8vNGyM0TS1Be38vkjy4JkCVHUptcJytNPzxxHLxw3geCO7BNcKDTLFRH0dkkBvAawRV3x4EKPGShP13fGIVAYHWHtvy2pBJPkUMO5/uwxtDx5ricRrHoPWiE/Tn7ir0CsKippSQC260WY+0Hz/14Wy92VH5P2NrqaU7FgoFR8i2Idlj2vGn/uir+MOFnbEXSB15o1hzTGDwclBomXVI7cKCQgvw5yK3hS4hyFtXoI7ZUM3l3jxjA9y4E4/tH1fowcFS1OMitW/ccMcNuUVhLjJ7GDGW5KQe3esKEu7i/ydzUxjK2v+BOvGu0ta+69XaDVff64tgqM0bPnY4j1ITHKM51tMKyiWn+Lc583Xcn6X5YErK/+O/+BVUm3uznoye5wYpeerFm9D97rPO0YUmE7L9eo9FO7WMjBc0Aii6NSUV6t8gvFv/QIbidGlU8MzFXCH0Pw+ZDeHVHBilBcE9KExb7wsTK1m62/ljBraCkAXJAogC5uVW17o4nw4dNoogHLpiUGVRmT1Ykl1Nksw7iVqJx/vfSs+6Gkw5Y+FcZtAYcPEqF5pAn0ZcNxgeOon8sUK7C8Jsnsh5iI24DOotCo9M='}}}