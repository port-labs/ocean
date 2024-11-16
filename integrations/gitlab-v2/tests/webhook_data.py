from choices import Entity


__GROUP = {
    "created_at": "2012-07-21T07:30:54Z",
    "updated_at": "2012-07-21T07:38:22Z",
    "event_name": "group_create",
    "name": "StoreCloud",
    "path": "storecloud",
    "group_id": 78,
}


__PROJECT = {
    "created_at": "2012-07-21T07:30:54Z",
    "updated_at": "2012-07-21T07:38:22Z",
    "event_name": "project_create",
    "name": "StoreCloud",
    "owner_email": "johnsmith@example.com",
    "owner_name": "John Smith",
    "owners": [{"name": "John", "email": "user1@example.com"}],
    "path": "storecloud",
    "path_with_namespace": "jsmith/storecloud",
    "project_id": 74,
    "project_visibility": "private",
}


__ISSUE = {
    "object_kind": "issue",
    "event_type": "issue",
    "user": {
        "id": 1,
        "name": "Administrator",
        "username": "root",
        "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon",
        "email": "admin@example.com",
    },
    "project": {
        "id": 1,
        "name": "Gitlab Test",
        "description": "Aut reprehenderit ut est.",
        "web_url": "http://example.com/gitlabhq/gitlab-test",
        "avatar_url": None,
        "git_ssh_url": "git@example.com:gitlabhq/gitlab-test.git",
        "git_http_url": "http://example.com/gitlabhq/gitlab-test.git",
        "namespace": "GitlabHQ",
        "visibility_level": 20,
        "path_with_namespace": "gitlabhq/gitlab-test",
        "default_branch": "master",
        "ci_config_path": None,
        "homepage": "http://example.com/gitlabhq/gitlab-test",
        "url": "http://example.com/gitlabhq/gitlab-test.git",
        "ssh_url": "git@example.com:gitlabhq/gitlab-test.git",
        "http_url": "http://example.com/gitlabhq/gitlab-test.git",
    },
    "object_attributes": {
        "id": 301,
        "title": "New API: create/update/delete file",
        "assignee_ids": [51],
        "assignee_id": 51,
        "author_id": 51,
        "project_id": 14,
        "created_at": "2013-12-03T17:15:43Z",
        "updated_at": "2013-12-03T17:15:43Z",
        "updated_by_id": 1,
        "last_edited_at": None,
        "last_edited_by_id": None,
        "relative_position": 0,
        "description": "Create new API for manipulations with repository",
        "milestone_id": None,
        "state_id": 1,
        "confidential": False,
        "discussion_locked": True,
        "due_date": None,
        "moved_to_id": None,
        "duplicated_to_id": None,
        "time_estimate": 0,
        "total_time_spent": 0,
        "time_change": 0,
        "human_total_time_spent": None,
        "human_time_estimate": None,
        "human_time_change": None,
        "weight": None,
        "health_status": "at_risk",
        "type": "Issue",
        "iid": 23,
        "url": "http://example.com/diaspora/issues/23",
        "state": "opened",
        "action": "open",
        "severity": "high",
        "escalation_status": "triggered",
        "escalation_policy": {"id": 18, "name": "Engineering On-call"},
        "labels": [
            {
                "id": 206,
                "title": "API",
                "color": "#ffffff",
                "project_id": 14,
                "created_at": "2013-12-03T17:15:43Z",
                "updated_at": "2013-12-03T17:15:43Z",
                "template": False,
                "description": "API related issues",
                "type": "ProjectLabel",
                "group_id": 41,
            }
        ],
    },
    "repository": {
        "name": "Gitlab Test",
        "url": "http://example.com/gitlabhq/gitlab-test.git",
        "description": "Aut reprehenderit ut est.",
        "homepage": "http://example.com/gitlabhq/gitlab-test",
    },
    "assignees": [
        {
            "name": "User1",
            "username": "user1",
            "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon",
        }
    ],
    "assignee": {
        "name": "User1",
        "username": "user1",
        "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon",
    },
    "labels": [
        {
            "id": 206,
            "title": "API",
            "color": "#ffffff",
            "project_id": 14,
            "created_at": "2013-12-03T17:15:43Z",
            "updated_at": "2013-12-03T17:15:43Z",
            "template": False,
            "description": "API related issues",
            "type": "ProjectLabel",
            "group_id": 41,
        }
    ],
    "changes": {
        "updated_by_id": {"previous": None, "current": 1},
        "updated_at": {
            "previous": "2017-09-15 16:50:55 UTC",
            "current": "2017-09-15 16:52:00 UTC",
        },
        "labels": {
            "previous": [
                {
                    "id": 206,
                    "title": "API",
                    "color": "#ffffff",
                    "project_id": 14,
                    "created_at": "2013-12-03T17:15:43Z",
                    "updated_at": "2013-12-03T17:15:43Z",
                    "template": False,
                    "description": "API related issues",
                    "type": "ProjectLabel",
                    "group_id": 41,
                }
            ],
            "current": [
                {
                    "id": 205,
                    "title": "Platform",
                    "color": "#123123",
                    "project_id": 14,
                    "created_at": "2013-12-03T17:15:43Z",
                    "updated_at": "2013-12-03T17:15:43Z",
                    "template": False,
                    "description": "Platform related issues",
                    "type": "ProjectLabel",
                    "group_id": 41,
                }
            ],
        },
    },
}


__MERGE_REQUEST = {
    "object_kind": "merge_request",
    "event_type": "merge_request",
    "user": {
        "id": 1,
        "name": "Administrator",
        "username": "root",
        "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon",
        "email": "admin@example.com",
    },
    "project": {
        "id": 1,
        "name": "Gitlab Test",
        "description": "Aut reprehenderit ut est.",
        "web_url": "http://example.com/gitlabhq/gitlab-test",
        "avatar_url": None,
        "git_ssh_url": "git@example.com:gitlabhq/gitlab-test.git",
        "git_http_url": "http://example.com/gitlabhq/gitlab-test.git",
        "namespace": "GitlabHQ",
        "visibility_level": 20,
        "path_with_namespace": "gitlabhq/gitlab-test",
        "default_branch": "master",
        "ci_config_path": "",
        "homepage": "http://example.com/gitlabhq/gitlab-test",
        "url": "http://example.com/gitlabhq/gitlab-test.git",
        "ssh_url": "git@example.com:gitlabhq/gitlab-test.git",
        "http_url": "http://example.com/gitlabhq/gitlab-test.git",
    },
    "repository": {
        "name": "Gitlab Test",
        "url": "http://example.com/gitlabhq/gitlab-test.git",
        "description": "Aut reprehenderit ut est.",
        "homepage": "http://example.com/gitlabhq/gitlab-test",
    },
    "object_attributes": {
        "id": 99,
        "iid": 1,
        "target_branch": "master",
        "source_branch": "ms-viewport",
        "source_project_id": 14,
        "author_id": 51,
        "assignee_ids": [6],
        "assignee_id": 6,
        "reviewer_ids": [6],
        "title": "MS-Viewport",
        "created_at": "2013-12-03T17:23:34Z",
        "updated_at": "2013-12-03T17:23:34Z",
        "last_edited_at": "2013-12-03T17:23:34Z",
        "last_edited_by_id": 1,
        "milestone_id": None,
        "state_id": 1,
        "state": "opened",
        "blocking_discussions_resolved": True,
        "work_in_progress": False,
        "draft": False,
        "first_contribution": True,
        "merge_status": "unchecked",
        "target_project_id": 14,
        "description": "",
        "prepared_at": "2013-12-03T19:23:34Z",
        "total_time_spent": 1800,
        "time_change": 30,
        "human_total_time_spent": "30m",
        "human_time_change": "30s",
        "human_time_estimate": "30m",
        "url": "http://example.com/diaspora/merge_requests/1",
        "source": {
            "name": "Awesome Project",
            "description": "Aut reprehenderit ut est.",
            "web_url": "http://example.com/awesome_space/awesome_project",
            "avatar_url": None,
            "git_ssh_url": "git@example.com:awesome_space/awesome_project.git",
            "git_http_url": "http://example.com/awesome_space/awesome_project.git",
            "namespace": "Awesome Space",
            "visibility_level": 20,
            "path_with_namespace": "awesome_space/awesome_project",
            "default_branch": "master",
            "homepage": "http://example.com/awesome_space/awesome_project",
            "url": "http://example.com/awesome_space/awesome_project.git",
            "ssh_url": "git@example.com:awesome_space/awesome_project.git",
            "http_url": "http://example.com/awesome_space/awesome_project.git",
        },
        "target": {
            "name": "Awesome Project",
            "description": "Aut reprehenderit ut est.",
            "web_url": "http://example.com/awesome_space/awesome_project",
            "avatar_url": None,
            "git_ssh_url": "git@example.com:awesome_space/awesome_project.git",
            "git_http_url": "http://example.com/awesome_space/awesome_project.git",
            "namespace": "Awesome Space",
            "visibility_level": 20,
            "path_with_namespace": "awesome_space/awesome_project",
            "default_branch": "master",
            "homepage": "http://example.com/awesome_space/awesome_project",
            "url": "http://example.com/awesome_space/awesome_project.git",
            "ssh_url": "git@example.com:awesome_space/awesome_project.git",
            "http_url": "http://example.com/awesome_space/awesome_project.git",
        },
        "last_commit": {
            "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
            "message": "fixed readme",
            "title": "Update file README.md",
            "timestamp": "2012-01-03T23:36:29+02:00",
            "url": "http://example.com/awesome_space/awesome_project/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
            "author": {"name": "GitLab dev user", "email": "gitlabdev@dv6700.(none)"},
        },
        "labels": [
            {
                "id": 206,
                "title": "API",
                "color": "#ffffff",
                "project_id": 14,
                "created_at": "2013-12-03T17:15:43Z",
                "updated_at": "2013-12-03T17:15:43Z",
                "template": False,
                "description": "API related issues",
                "type": "ProjectLabel",
                "group_id": 41,
            }
        ],
        "action": "open",
        "detailed_merge_status": "mergeable",
    },
    "labels": [
        {
            "id": 206,
            "title": "API",
            "color": "#ffffff",
            "project_id": 14,
            "created_at": "2013-12-03T17:15:43Z",
            "updated_at": "2013-12-03T17:15:43Z",
            "template": False,
            "description": "API related issues",
            "type": "ProjectLabel",
            "group_id": 41,
        }
    ],
    "changes": {
        "updated_by_id": {"previous": None, "current": 1},
        "draft": {"previous": True, "current": False},
        "updated_at": {
            "previous": "2017-09-15 16:50:55 UTC",
            "current": "2017-09-15 16:52:00 UTC",
        },
        "labels": {
            "previous": [
                {
                    "id": 206,
                    "title": "API",
                    "color": "#ffffff",
                    "project_id": 14,
                    "created_at": "2013-12-03T17:15:43Z",
                    "updated_at": "2013-12-03T17:15:43Z",
                    "template": False,
                    "description": "API related issues",
                    "type": "ProjectLabel",
                    "group_id": 41,
                }
            ],
            "current": [
                {
                    "id": 205,
                    "title": "Platform",
                    "color": "#123123",
                    "project_id": 14,
                    "created_at": "2013-12-03T17:15:43Z",
                    "updated_at": "2013-12-03T17:15:43Z",
                    "template": False,
                    "description": "Platform related issues",
                    "type": "ProjectLabel",
                    "group_id": 41,
                }
            ],
        },
        "last_edited_at": {"previous": None, "current": "2023-03-15 00:00:10 UTC"},
        "last_edited_by_id": {"previous": None, "current": 3278533},
    },
    "assignees": [
        {
            "id": 6,
            "name": "User1",
            "username": "user1",
            "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon",
        }
    ],
    "reviewers": [
        {
            "id": 6,
            "name": "User1",
            "username": "user1",
            "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon",
        }
    ],
}


WEBHOOK_DATA = {
    Entity.GROUP.value: __GROUP,
    Entity.PROJECT.value: __PROJECT,
    Entity.MERGE_REQUEST.value: __MERGE_REQUEST,
    Entity.ISSUE.value: __ISSUE,
}