from typing import Literal

IssueStatusLiteral = Literal["all", "open", "ignored", "snoozed", "closed"]
IssueSeverityLiteral = Literal["critical", "high", "medium", "low"]
IssueTypeLiteral = Literal[
    "open_source",
    "leaked_secret",
    "cloud",
    "sast",
    "iac",
    "docker_container",
    "cloud_instance",
    "surface_monitoring",
    "malware",
    "eol",
    "mobile",
    "scm_security",
    "ai_pentest",
    "license",
    "app_level_open_source",
]
