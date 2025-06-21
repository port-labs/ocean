import os

class Config:
    SPACELIFT_API_URL = "https://api.spacelift.io/graphql"
    SPACELIFT_TOKEN = os.getenv("SPACELIFT_TOKEN")  # Will rotate handled in auth
    ENABLED_KINDS = os.getenv("ENABLED_KINDS", "").split(",")

    PORT_CLIENT_ID = os.getenv("PORT_CLIENT_ID")
    PORT_CLIENT_SECRET = os.getenv("PORT_CLIENT_SECRET")
    PORT_BASE_URL = os.getenv("PORT_BASE_URL", "https://api.getport.io/v1")

    BLUEPRINT_CONFIG = {
        "run_status_filter": os.getenv("RUN_STATUS_FILTER", "finished"),
        "run_days_back": int(os.getenv("RUN_DAYS_BACK", "7")),
    }
