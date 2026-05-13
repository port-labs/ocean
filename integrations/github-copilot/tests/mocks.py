organizations_response = [
    {
        "login": "github",
        "id": 1,
        "node_id": "MDEyOk9yZ2FuaXphdGlvbjE=",
        "url": "https://api.github.com/orgs/github",
        "repos_url": "https://api.github.com/orgs/github/repos",
        "events_url": "https://api.github.com/orgs/github/events",
        "hooks_url": "https://api.github.com/orgs/github/hooks",
        "issues_url": "https://api.github.com/orgs/github/issues",
        "members_url": "https://api.github.com/orgs/github/members{/member}",
        "public_members_url": "https://api.github.com/orgs/github/public_members{/member}",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "description": "A great organization",
    }
]


mock_copilot_28_day_manifest_response = {
    "download_links": [
        "https://signed.example.com/copilot-report-part-1.json",
        "https://signed.example.com/copilot-report-part-2.json",
    ],
    "report_start_day": "2026-02-01",
    "report_end_day": "2026-02-28",
}

mock_copilot_schema_a_day_totals_wrapper = {
    "report_start_day": "2026-02-01",
    "report_end_day": "2026-02-28",
    "day_totals": [
        {
            "org": "acme-corp-test-org",
            "daily_active_users": 42,
            "day": "2026-03-05",
            "code_generation_activity_count": 150,
        }
    ],
}

# Single JSON object — small orgs with little Copilot activity produce this format.
# response.json() handles this correctly.
mock_single_json_signed_url_content = (
    '{"report_start_day":"2026-01-01","report_end_day":"2026-01-28","day_totals":[{"org":"small-test-org","daily_active_users":1,"day":"2026-01-15","code_generation_activity_count":3}]}'
).encode()

# Reproduces the real GitHub API response format for signed URLs:
# NDJSON — two JSON objects separated by a newline, as seen in production.
# response.json() crashes with "Extra data: line 2 column 1" on this content.
mock_ndjson_signed_url_content = (
    '{"report_start_day":"2026-02-01","report_end_day":"2026-02-28","day_totals":[{"org":"acme-corp-test-org","daily_active_users":5,"day":"2026-02-01","code_generation_activity_count":100}]}\n'
    '{"report_start_day":"2026-02-01","report_end_day":"2026-02-28","day_totals":[{"org":"acme-corp-test-org","daily_active_users":42,"day":"2026-03-05","code_generation_activity_count":150}]}'
).encode()
