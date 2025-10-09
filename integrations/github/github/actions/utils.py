def build_external_id(workflow_run: dict[str, Any]) -> str:
    return f'gh_{workflow_run["repository"]["owner"]["id"]}_{workflow_run["repository"]["id"]}_{workflow_run["id"]}'
