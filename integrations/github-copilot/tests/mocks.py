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

copilot_billing_response = {
    "seat_breakdown": {
        "total": 12,
        "added_this_cycle": 9,
        "pending_invitation": 0,
        "pending_cancellation": 0,
        "active_this_cycle": 12,
        "inactive_this_cycle": 11,
    },
    "seat_management_setting": "assign_selected",
    "ide_chat": "enabled",
    "platform_chat": "enabled",
    "cli": "enabled",
    "public_code_suggestions": "block",
    "plan_type": "business",
}

copilot_seat_assignments_response = {
    "total_seats": 2,
    "seats": [
        {
            "created_at": "2021-08-03T18:00:00-06:00",
            "updated_at": "2021-09-23T15:00:00-06:00",
            "pending_cancellation_date": None,
            "last_activity_at": "2021-10-14T00:53:32-06:00",
            "last_activity_editor": "vscode/1.77.3/copilot/1.86.82",
            "last_authenticated_at": "2021-10-14T00:53:32-06:00",
            "plan_type": "business",
            "assignee": {
                "login": "octocat",
                "id": 1,
                "node_id": "MDQ6VXNlcjE=",
                "avatar_url": "https://github.com/images/error/octocat_happy.gif",
                "gravatar_id": "",
                "url": "https://api.github.com/users/octocat",
                "html_url": "https://github.com/octocat",
                "type": "User",
                "site_admin": False,
            },
            "assigning_team": {
                "id": 1,
                "node_id": "MDQ6VGVhbTE=",
                "url": "https://api.github.com/teams/1",
                "html_url": "https://github.com/orgs/github/teams/justice-league",
                "name": "Justice League",
                "slug": "justice-league",
                "description": "A great team.",
                "privacy": "closed",
                "permission": "admin",
            },
        },
        {
            "created_at": "2021-09-23T18:00:00-06:00",
            "updated_at": "2021-09-23T15:00:00-06:00",
            "pending_cancellation_date": "2021-11-01",
            "last_activity_at": "2021-10-13T00:53:32-06:00",
            "last_activity_editor": "vscode/1.77.3/copilot/1.86.82",
            "last_authenticated_at": "2021-10-14T00:53:32-06:00",
            "plan_type": "business",
            "assignee": {
                "login": "octokitten",
                "id": 2,
                "node_id": "MDQ76VNlcjE=",
                "avatar_url": "https://github.com/images/error/octokitten_happy.gif",
                "gravatar_id": "",
                "url": "https://api.github.com/users/octokitten",
                "html_url": "https://github.com/octokitten",
                "type": "User",
                "site_admin": False,
            },
        },
    ],
}

copilot_user_seat_response = {
    "created_at": "2021-08-03T18:00:00-06:00",
    "updated_at": "2021-09-23T15:00:00-06:00",
    "pending_cancellation_date": None,
    "last_activity_at": "2021-10-14T00:53:32-06:00",
    "last_activity_editor": "vscode/1.77.3/copilot/1.86.82",
    "last_authenticated_at": "2021-10-14T00:53:32-06:00",
    "plan_type": "business",
    "assignee": {
        "login": "octocat",
        "id": 1,
        "node_id": "MDQ6VXNlcjE=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": "https://api.github.com/users/octocat",
        "html_url": "https://github.com/octocat",
        "type": "User",
        "site_admin": False,
    },
    "assigning_team": {
        "id": 1,
        "node_id": "MDQ6VGVhbTE=",
        "url": "https://api.github.com/teams/1",
        "html_url": "https://github.com/orgs/github/teams/justice-league",
        "name": "Justice League",
        "slug": "justice-league",
        "description": "A great team.",
        "privacy": "closed",
        "permission": "admin",
    },
}
