WEBHOOK_PATH = "/webhook"


def build_integration_webhook_url(app_host: str) -> str:
    return f"{app_host.rstrip('/')}/integration{WEBHOOK_PATH}"
