# github

An integration used to import github resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/) *Replace this link with a link to this integration's documentation*

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)

## Pull request review stats

`includeReviewStats` defaults to false, is independent of `includeComments`, and is not part of the default mapping. Add another `pull-request` block for the pull requests that should store review numbers, and leave the default block unchanged.

Limit that block with `repoSearch` and `states`. The integration applies both before it calls the review and timeline APIs. A bot is a GitHub user whose type is `Bot`.

```yaml
- kind: pull-request
  selector:
    query: 'true'
    repoSearch:
      query: 'org:my-org'
    states:
      - open
    includeReviewStats: true
  port:
    entity:
      mappings:
        identifier: .head.repo.name + (.id|tostring)
        title: .title
        blueprint: '"githubPullRequest"'
        properties:
          humanApprovals: .__reviewStats.humanApprovals
          humanComments: .__reviewStats.humanComments
          botComments: .__reviewStats.botComments
          firstHumanReview: .__reviewStats.firstHumanReview
          firstApproval: .__reviewStats.firstApproval
          waitOnHumanHours: .__reviewStats.waitOnHumanHours
```