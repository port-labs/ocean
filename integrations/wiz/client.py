# Python 3.9+
# pip(3) install requests==2.28.1
import json
import re
import time
import logging
import requests

"""
README
------
Description: This script checks the service account permissions
Dependencies: Python 3.9+, requests==2.28.1
How to use the script:
    1) Add your client ID, client secret, token URL, and API endpoint URL
"""

DEBUG_LOG = False

# Add your client ID, client secret, token URL, and API endpoint URL
client_id = "YOUR-CLIENT-ID"
client_secret = "YOUR-CLIENT-SECRET"
token_url = "YOUR-TOKEN-URL"  # e.g. https://auth.app.wiz.io/oauth/token
api_endpoint_url = "YOUR-API-ENDPOINT-URL"  # e.g. https://api.eu3.app.wiz.io/graphql

# Configuration variables
MAX_RETRIES_FOR_QUERY = 5
RETRY_TIME_FOR_QUERY = 2

# Private and global variables
AUDIENCE = ""
SERVICE_ACCOUNT_DETAILS = {}
AUTH0_URLS = ["https://auth.wiz.io/oauth/token", "https://auth0.gov.wiz.io/oauth/token"]
COGNITO_URLS = [
    "https://auth.app.wiz.io/oauth/token",
    "https://auth.gov.wiz.io/oauth/token",
]
global_token = ""

# The GraphQL query that defines which data you wish to fetch.
VIEWER_QUERY = """
    query SecurityFrameworks {
      securityFrameworks(first: 100) {
        nodes {
          id
        }
      }
    }
    """


def get_token(client_id, client_secret, token_url):
    global global_token
    logging.debug("Getting a token")
    response = requests.post(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=generate_authentication_params(client_id, client_secret, token_url),
    )
    if response.status_code != requests.codes.ok:
        raise Exception(
            f"Error authenticating to Wiz [{response.status_code}] - {response.text}"
        )
    response_json = response.json()
    new_token = response_json.get("access_token")
    if not new_token:
        raise Exception(
            f'Could not retrieve token from Wiz: {response_json.get("message")}'
        )
    logging.debug("Received a token")
    global_token = new_token


def generate_authentication_params(client_id, client_secret, token_url):
    global AUDIENCE
    if token_url in AUTH0_URLS:
        AUDIENCE = "beyond-api"
        return {
            "grant_type": "client_credentials",
            "audience": AUDIENCE,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    elif token_url in COGNITO_URLS:
        AUDIENCE = "wiz-api"
        return {
            "grant_type": "client_credentials",
            "audience": AUDIENCE,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    else:
        raise Exception("Invalid Token URL")


# The method sends query/mutation to Wiz API and returns data from Wiz according to the query and the variables If
# the method receives one of the status codes: 401, 403, 404, it will raise an error accordingly. In addition,
# if the method receives a status code other than 200, it waits a number of seconds (according RETRY_TIME_FOR_QUERY)
# and try to send a request again. The methods has a max number of retries before raising an error (according
# MAX_RETRIES_FOR_QUERY).
def query(query, variables):
    retries = 0
    response = send_request(query, variables)
    logging.debug(
        f"The API response status code is {response.status_code}\n"
        f"response text is {json.loads(response.text)}\n"
        f"response content is {json.loads(response.content)}"
    )
    code = response.status_code
    if code == requests.codes.unauthorized or code == requests.codes.forbidden:
        raise Exception(
            f"Error authenticating to Wiz [{response.status_code}] - {response.text}"
        )
    elif code == requests.codes.not_found:
        raise Exception(
            f"Error authenticating to Wiz [{response.status_code}] - check your api endpoint url"
        )
    while code != requests.codes.ok:
        if retries >= MAX_RETRIES_FOR_QUERY:
            raise Exception(
                f"Exceeding the maximum number of retries. Error authenticating to Wiz [{response.status_code}] - {response.text}"
            )
        logging.info(
            "Error authenticating to Wiz [%d] - %s. Waiting %.2f seconds and sending again a request to Wiz API",
            response.status_code,
            response.text,
            MAX_RETRIES_FOR_QUERY,
        )
        time.sleep(RETRY_TIME_FOR_QUERY)
        response = send_request(query, variables)
        code = response.status_code
        retries += 1
    response_json = response.json()
    data = response_json.get("data")
    if data or not "access denied" in response.text:
        raise Exception(f"There was an error while running this API.")
    logging.debug("Request sent successfully and received response with data")
    return response.text


def send_request(query, variables):
    logging.debug(
        f"Sending a request to Wiz API\nQuery: {query}\nVariables: {variables}"
    )
    if global_token:
        return requests.post(
            api_endpoint_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + global_token,
            },
            json={"query": query, "variables": variables},
        )
    raise Exception("An access token is missing.")


def validate_parameters():
    """
    This function validates the input parameters
    :raise: Exception if the parameters are not correct
    """
    if (
        client_id == "YOUR-CLIENT-ID"
        or client_secret == "YOUR-CLIENT-SECRET"
        or token_url == "YOUR-TOKEN-URL"
        or api_endpoint_url == "YOUR-API-ENDPOINT-URL"
    ):
        raise Exception(f"Please fill Wiz parameters.\n")


def get_api_permissions():
    global SERVICE_ACCOUNT_DETAILS
    logging.debug(f"Checking API Permissions")

    viewer_variables = {}
    viewer_response_text = query(VIEWER_QUERY, viewer_variables)

    pattern = r"your permissions: \[[a-z:]*\]"
    permissions_not_parsed = re.findall(pattern, viewer_response_text)
    if len(permissions_not_parsed) == 0:
        raise Exception(
            f"There was an error parsing the permissions in {viewer_response_text}"
        )

    permissions_str = re.sub(r"your permissions: ", "", permissions_not_parsed[0])
    return permissions_str


def print_api_info(api_permissions):
    api_info_str = (
        f"\n****** API Information ******\n"
        f"\tUser Input\n"
        f"\t\tClient ID: {client_id}\n"
        f"\t\tClient Secret: {client_secret}\n"
        f"\t\tToken URL: {token_url}\n"
        f"\t\tAPI Endpoint URL: {api_endpoint_url}\n"
        f"\tService account details\n"
        f"\t\tPermissions: {api_permissions[1:-1]}\n"
        f"\tRelated Parameters\n"
        f"\t\tAudience: {AUDIENCE}\n"
    )
    logging.info(api_info_str)


def main():
    try:
        log_level = logging.DEBUG if DEBUG_LOG else logging.INFO
        logging.basicConfig(
            format="%(asctime)s - [%(levelname)s] - %(message)s", level=log_level
        )
        logging.debug("Starting to check service account information from Wiz")

        validate_parameters()

        get_token(client_id, client_secret, token_url)

        api_permissions = get_api_permissions()

        print_api_info(api_permissions)

    except Exception as error:
        logging.error("An exception has been raised: \n%s", error)


if __name__ == "__main__":
    main()
