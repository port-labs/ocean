from bitbucket_ocean.auth import get_auth_token

def test_get_auth_token():
    token = get_auth_token("user", "password")
    assert isinstance(token, str)
