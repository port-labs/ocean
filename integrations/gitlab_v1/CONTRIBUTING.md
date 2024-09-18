# Contributing to Ocean - gitlab_v1

## Running Locally

Before running the `gitlab_v1` locally, follow these instructions to ensure everything is properly set up. This includes obtaining a GitLab personal token, configuring your `gitlab_config.yaml` file, and adding any additional resources.

### How to Obtain a GitLab Personal Token

To interact with the GitLab API, you'll need a personal access token. Follow these steps to create one:

1. **Login to GitLab**: Go to your GitLab instance and log in to your account.
2. **Access Settings**: Click on your profile icon in the top right corner, then select **Settings**.
3. **Access Tokens**: In the left-hand menu, navigate to [**Access Tokens**](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) under the **User** section.
4. **Generate Token**:
   - Name: Provide a descriptive name for your token (e.g., "API Access Token").
   - Scopes: Check the scopes you need. Common scopes include `api`, `read_user`, and `read_repository`.
   - Click **Create Personal Access Token**.
5. **Save Token**: Copy the generated token and store it securely. You will not be able to see it again after leaving the page.

### Configuring the `gitlab_config.yaml`

Once you have your GitLab token, configure the `gitlab_config.yaml` file. This file allows you to define the parameters for each resource type you'd like to fetch from GitLab, such as groups, projects, merge requests, and issues.

Here's an example configuration:

```yaml
groups:
  params:
   scope: 'all'        # Fetches all groups
   owned: true         # Limits results to groups you own
  additional_data:
   - projects          # Include associated projects for each group
   - members           # Include group members

projects:
  params:
   owned: true         # Limits results to projects you own
  additional_data:
   - languages         # Fetch programming languages used in the project

merge_requests:
  params:
   scope: 'all'        # Fetch all merge requests
   state: 'opened'     # Limits to merge requests that are open
  additional_data:
   - approvals         # Include approval information for each merge request

issues:
  params:
   scope: 'all'        # Fetch all issues
  additional_data:
   - notes             # Include comments and notes on the issue
   - assignees         # Include assigned users
   - labels            # Include associated labels

events:
  - push               # Push events
  - tag_push           # Tag push events
  - issue              # Issue events
  - note               # Comment or note events
  - merge_request      # Merge request events
  - wiki_page          # Wiki page events
  - pipeline           # Pipeline events
  - job                # Job events
  - deployment         # Deployment events
  - feature_flag       # Feature flag events
  - release            # Release events
  - project_token      # Project token events
  - group_token        # Group token events
```
Additional Notes:
Credentials Setup: Ensure your GitLab token is set up in the environment or properly configured in your tool before making any API requests.
