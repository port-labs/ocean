def build_external_id(project_id: int | str, pipeline_id: int | str) -> str:
    return f"gl_{project_id}_{pipeline_id}"
