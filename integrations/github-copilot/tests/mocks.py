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

teams_response = [
    {
        "id": 1,
        "node_id": "MDQ6VGVhbTE=",
        "url": "https://api.github.com/teams/1",
        "html_url": "https://github.com/orgs/github/teams/justice-league",
        "name": "Justice League",
        "slug": "justice-league",
        "description": "A great team.",
        "privacy": "closed",
        "notification_setting": "notifications_enabled",
        "permission": "admin",
        "members_url": "https://api.github.com/teams/1/members{/member}",
        "repositories_url": "https://api.github.com/teams/1/repos",
        "parent": None,
    }
]

copilot_metrics_response = [
    {
        "date": "2024-06-24",
        "total_active_users": 24,
        "total_engaged_users": 20,
        "copilot_ide_code_completions": {
            "total_engaged_users": 20,
            "languages": [
                {"name": "python", "total_engaged_users": 10},
                {"name": "ruby", "total_engaged_users": 10},
            ],
            "editors": [
                {
                    "name": "vscode",
                    "total_engaged_users": 13,
                    "models": [
                        {
                            "name": "default",
                            "is_custom_model": False,
                            "custom_model_training_date": None,
                            "total_engaged_users": 13,
                            "languages": [
                                {
                                    "name": "python",
                                    "total_engaged_users": 6,
                                    "total_code_suggestions": 249,
                                    "total_code_acceptances": 123,
                                    "total_code_lines_suggested": 225,
                                    "total_code_lines_accepted": 135,
                                },
                                {
                                    "name": "ruby",
                                    "total_engaged_users": 7,
                                    "total_code_suggestions": 496,
                                    "total_code_acceptances": 253,
                                    "total_code_lines_suggested": 520,
                                    "total_code_lines_accepted": 270,
                                },
                            ],
                        }
                    ],
                },
                {
                    "name": "neovim",
                    "total_engaged_users": 7,
                    "models": [
                        {
                            "name": "a-custom-model",
                            "is_custom_model": True,
                            "custom_model_training_date": "2024-02-01",
                            "languages": [
                                {
                                    "name": "typescript",
                                    "total_engaged_users": 3,
                                    "total_code_suggestions": 112,
                                    "total_code_acceptances": 56,
                                    "total_code_lines_suggested": 143,
                                    "total_code_lines_accepted": 61,
                                },
                                {
                                    "name": "go",
                                    "total_engaged_users": 4,
                                    "total_code_suggestions": 132,
                                    "total_code_acceptances": 67,
                                    "total_code_lines_suggested": 154,
                                    "total_code_lines_accepted": 72,
                                },
                            ],
                        }
                    ],
                },
            ],
        },
        "copilot_ide_chat": {
            "total_engaged_users": 13,
            "editors": [
                {
                    "name": "vscode",
                    "total_engaged_users": 13,
                    "models": [
                        {
                            "name": "default",
                            "is_custom_model": False,
                            "custom_model_training_date": None,
                            "total_engaged_users": 12,
                            "total_chats": 45,
                            "total_chat_insertion_events": 12,
                            "total_chat_copy_events": 16,
                        },
                        {
                            "name": "a-custom-model",
                            "is_custom_model": True,
                            "custom_model_training_date": "2024-02-01",
                            "total_engaged_users": 1,
                            "total_chats": 10,
                            "total_chat_insertion_events": 11,
                            "total_chat_copy_events": 3,
                        },
                    ],
                }
            ],
        },
        "copilot_dotcom_chat": {
            "total_engaged_users": 14,
            "models": [
                {
                    "name": "default",
                    "is_custom_model": False,
                    "custom_model_training_date": None,
                    "total_engaged_users": 14,
                    "total_chats": 38,
                }
            ],
        },
        "copilot_dotcom_pull_requests": {
            "total_engaged_users": 12,
            "repositories": [
                {
                    "name": "demo/repo1",
                    "total_engaged_users": 8,
                    "models": [
                        {
                            "name": "default",
                            "is_custom_model": False,
                            "custom_model_training_date": None,
                            "total_pr_summaries_created": 6,
                            "total_engaged_users": 8,
                        }
                    ],
                },
                {
                    "name": "demo/repo2",
                    "total_engaged_users": 4,
                    "models": [
                        {
                            "name": "a-custom-model",
                            "is_custom_model": True,
                            "custom_model_training_date": "2024-02-01",
                            "total_pr_summaries_created": 10,
                            "total_engaged_users": 4,
                        }
                    ],
                },
            ],
        },
    }
]
