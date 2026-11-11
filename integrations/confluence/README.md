# Confluence

Sync Confluence Cloud spaces, pages, and users into Port.

Spaces and pages use the [Confluence Cloud REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/intro/). Users use [search users](https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-search/#api-wiki-rest-api-search-user-get). This integration does not support Confluence Data Center.

## Prerequisites

Create an API token for an Atlassian account that can view the content you want in the catalog:

1. Open [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) and create a token.
2. Use that account's email address and the token as basic auth. The account needs permission to view spaces, pages, and user profiles. See [basic auth for Confluence REST APIs](https://developer.atlassian.com/cloud/confluence/basic-auth-for-rest-apis/).

## Configuration

| Spec field | Required | Description |
| --- | --- | --- |
| `confluenceHostUrl` | Yes | Cloud site URL, for example `https://example.atlassian.net`. |
| `confluenceUserEmail` | Yes | Atlassian account email. Stored as a secret. |
| `confluenceApiToken` | Yes | API token for that account. Stored as a secret. |

Copy `.env.example` to `.env` for local Ocean runs and fill in the Port and Confluence values. Do not commit `.env`.

## Resources

| Kind | Confluence API | Port blueprint | Relations |
| --- | --- | --- | --- |
| `space` | `GET /wiki/api/v2/spaces` | `confluenceSpace` | Author and owner |
| `page` | `GET /wiki/api/v2/pages` | `confluencePage` | Space, parent page, author, and owner |
| `user` | `GET /wiki/rest/api/search/user?cql=type=user` | `confluenceUser` | None |

Spaces are synced without a type or status filter unless the selector sets one. Pages default to current pages in every space, with the markdown body included, unless `spaceIds` is set. Users default to every permission type (`sitePermissionType: all`). Confluence returns at most 10,000 users for `cql=type=user`.

Space and page list calls follow `_links.next`. User search uses `start` and `limit`.

### Selectors

| Selector | Kind | Default | Effect |
| --- | --- | --- | --- |
| `type` | space | unset | Only this space type: `global`, `collaboration`, `knowledge_base`, `personal`, `system`, `onboarding`, `xflow_sample_space`. |
| `status` | space | unset | Only this status: `current`, `archived`, `trashed`. |
| `labels` | space | `[]` | Spaces that have all of these labels. |
| `spaceIds` | page | `[]` | Only pages in these space ids. Sent as `space-id`. |
| `includeArchived` | page | `false` | Also fetch archived pages. |
| `includeBody` | page | `true` | Fetch each page body as markdown. Responses get larger, so the page size drops to 25. |
| `sitePermissionType` | user | `all` | `all`, `none` (licensed users), or `externalCollaborator`. |

Space descriptions are requested as plain text on the same spaces call.

## Rate limits

Confluence Cloud applies burst limits to API-token traffic and returns HTTP 429 with `Retry-After`. Ocean's HTTP client retries those responses. Details are in the [Confluence rate limiting](https://developer.atlassian.com/cloud/confluence/rate-limiting/) guide.

## Troubleshooting

- **401**: The email or API token was rejected. Create a new token and confirm the email is the Atlassian account email, not a Confluence display name.
- **403**: The account cannot view that content. Grant view access to the spaces and user profiles you expect to sync, then run the sync again.
- **429**: The site asked the integration to slow down. The client retries. If it continues, set a space `type` or `status`, or leave `includeBody` off.
- **Empty catalog**: Confirm the site URL is the Cloud origin, such as `https://example.atlassian.net`, and that the mapped kinds are `space`, `page`, and `user`.

## Local development

```bash
cd integrations/confluence
make install
. .venv/bin/activate
make test
make lint
```

Fill in `.env`, then run `make run` only against a Confluence site you are allowed to read.
