# Jira

An integration used to import Jira resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/jira)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)

## Issue comments

`includeComments` defaults to false and is not part of the default mapping. Add another `issue` block and set its `jql` to the issues that should carry comments. JQL runs before the comments API. Leave the default issue block unchanged.

```yaml
- kind: issue
  selector:
    query: 'true'
    jql: 'key in (PROJ-1, PROJ-2)'
    includeComments: true
  port:
    itemsToParse: .__comments
    entity:
      mappings:
        identifier: .item.__commentId
        title: .item.__body // "" | .[0:120]
        blueprint: '"jiraIssueComment"'
        properties:
          body: .item.__body
          author: .item.author.emailAddress // .item.author.displayName // .item.author.accountId
          createdAt: .item.created
          updatedAt: .item.updated
          url: .item.__url
        relations:
          issue: .key
```

Comment items keep Jira's raw fields. `__commentId` is `{issueKey}/{id}`. `__body` is the comment body flattened from ADF. `__url` is the browse URL.