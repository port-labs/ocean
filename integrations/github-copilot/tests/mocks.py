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

copilot_usage_report_manifest = {
    "download_links": [
        "https://signed.example.com/copilot-report-part-1.json",
        "https://signed.example.com/copilot-report-part-2.json",
    ],
    "report_start_day": "2025-07-01",
    "report_end_day": "2025-07-28",
}

copilot_usage_report_part_1 = [
    {"org": "acme-corp-test-org", "total_active_users": 42},
]

copilot_usage_report_part_2 = [
    {"org": "some-github-enterprise-corp", "total_active_users": 18},
]
