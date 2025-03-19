import httpx
import base64
import json
import asyncio

# Replace with your webhook's URL
group_id = 66136652
WEBHOOK_URL = "http://localhost:8000/integration/hook/{group_id}".format(
    group_id=group_id
)
print(WEBHOOK_URL)


def create_mock_event(id: int) -> dict[str, dict[str, str]]:
    push_data = {
        "object_kind": "push",
        "event_name": "push",
        "before": "95790bf891e76fee5e1747ab589903a6a1f80f22",
        "after": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
        "ref": "refs/heads/master",
        "ref_protected": True,
        "checkout_sha": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
        "user_id": 4,
        "user_name": "John Smith",
        "user_username": "jsmith",
        "user_email": "john@example.com",
        "user_avatar": "https://s.gravatar.com/avatar/d4c74594d841139328695756648b6bd6?s=8://s.gravatar.com/avatar/d4c74594d841139328695756648b6bd6?s=80",
        "project_id": 45040836,
        "project": {
            "id": 45040836,
            "name": "Diaspora",
            "description": "",
            "web_url": "http://example.com/mike/diaspora",
            "avatar_url": None,
            "git_ssh_url": "git@example.com:mike/diaspora.git",
            "git_http_url": "http://example.com/mike/diaspora.git",
            "namespace": "Mike",
            "visibility_level": 0,
            "path_with_namespace": "mike/diaspora",
            "default_branch": "master",
            "homepage": "http://example.com/mike/diaspora",
            "url": "git@example.com:mike/diaspora.git",
            "ssh_url": "git@example.com:mike/diaspora.git",
            "http_url": "http://example.com/mike/diaspora.git",
        },
        "repository": {
            "name": "Diaspora",
            "url": "git@example.com:mike/diaspora.git",
            "description": "",
            "homepage": "http://example.com/mike/diaspora",
            "git_http_url": "http://example.com/mike/diaspora.git",
            "git_ssh_url": "git@example.com:mike/diaspora.git",
            "visibility_level": 0,
        },
        "commits": [
            {
                "id": "b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
                "message": "Update Catalan translation to e38cb41.\n\nSee https://gitlab.com/gitlab-org/gitlab for more information",
                "title": "Update Catalan translation to e38cb41.",
                "timestamp": "2011-12-12T14:27:31+02:00",
                "url": "http://example.com/mike/diaspora/commit/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
                "author": {"name": "Jordi Mallach", "email": "jordi@softcatala.org"},
                "added": ["CHANGELOG"],
                "modified": ["app/controller/application.rb"],
                "removed": [],
            },
            {
                "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
                "message": "fixed readme",
                "title": "fixed readme",
                "timestamp": "2012-01-03T23:36:29+02:00",
                "url": "http://example.com/mike/diaspora/commit/da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
                "author": {
                    "name": "GitLab dev user",
                    "email": "gitlabdev@dv6700.(none)",
                },
                "added": ["CHANGELOG"],
                "modified": ["app/controller/application.rb"],
                "removed": [],
            },
        ],
        "total_commits_count": 4,
    }

    return push_data


async def send_mock_event(id: int) -> None:
    mock_event = create_mock_event(id)
    async with httpx.AsyncClient() as client:
        client.headers["X-Gitlab-Event"] = "Push Hook"
        response = await client.post(WEBHOOK_URL, json=mock_event)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")


async def main():

    while True:
        tasks = []
        for j in range(10):
            tasks.append(send_mock_event(j + 1))
        await asyncio.gather(*tasks)


async def run_once():
    await send_mock_event(1)


if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(run_once())
