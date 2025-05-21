from port_ocean.context.ocean import ocean


def app_configured() -> bool:
    app_id = ocean.integration_config.get("app_id")
    app_private_key = ocean.integration_config.get("app_private_key")

    return app_id is not None and app_private_key is not None


def validate_passed_config() -> None:
    github_token = ocean.integration_config.get("github_token")

    if not app_configured() and not github_token:
        raise ValueError(
            "When Github app details are not passed, Github Personal Access Token must be passed."
        )
