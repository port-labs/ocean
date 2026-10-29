# Response-extensions key under which the retry transport records the GraphQL
# variables it actually sent. httpx resets `response.request` to the caller's
# original request once the transport returns, so variables the retry loop
# rewrote (e.g. a shrunk `variables.first`) survive only here for the GraphQL
# client's error logs. Shared contract between the transport (producer) and the
# GraphQL client (consumer).
from port_ocean.helpers.retry import SKIP_RETRY_EXTENSION_KEY

GRAPHQL_SENT_VARIABLES_EXTENSION = "github_graphql_sent_variables"
SKIP_RETRY_CONFIG = {SKIP_RETRY_EXTENSION_KEY: True}
