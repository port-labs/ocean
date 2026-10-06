def build_external_id(project_id: str, pipeline_id: str, run_id: str) -> str:
    return f"ado_{project_id}_{pipeline_id}_{run_id}"
