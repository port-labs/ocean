# gitlab-v2

An integration used to import gitlab-v2 resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/) *Replace this link with a link to this integration's documentation*

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)

## Merge request comments

`includeComments` defaults to false and is not part of the default mapping. Add another `merge-request` block for the merge requests that should carry notes, and leave the default block unchanged.

Limit that block with `states` and `updatedAfter`. The integration applies both before it calls the notes API.

```yaml
- kind: merge-request
  selector:
    query: 'true'
    states:
      - opened
    updatedAfter: 14
    includeComments: true
  port:
    itemsToParse: .__comments
    entity:
      mappings:
        identifier: .item.__commentId
        title: .item.body // "" | .[0:120]
        blueprint: '"gitlabMergeRequestComment"'
        properties:
          body: .item.body
          author: .item.author.username // .item.author.name
          createdAt: .item.created_at
          updatedAt: .item.updated_at // .item.created_at
          url: .item.url
          commentType: .item.__commentType
        relations:
          mergeRequest: .id | tostring
```

Note items keep GitLab's raw fields. `__commentId` is `{mergeRequestId}/{noteId}`. `__commentType` is `review` for a DiffNote and `comment` otherwise.