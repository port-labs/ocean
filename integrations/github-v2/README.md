# GitHub Integration for Port Ocean

This integration allows you to sync GitHub resources (repositories, pull requests, issues, teams, and workflows) with Port.

## Features

- **Repository Sync**: Sync all accessible repositories with their metadata
- **Pull Request Sync**: Sync pull requests from all repositories
- **Issue Sync**: Sync issues from all repositories (excluding pull requests)
- **Team Sync**: Sync teams from all accessible organizations
- **Workflow Sync**: Sync GitHub Actions workflows from all repositories
- **Live Events**: Real-time updates via webhooks (coming soon)

## Configuration

### Required Configuration

- `githubToken`: GitHub personal access token or GitHub App token
- `githubHost`: GitHub API host (defaults to https://api.github.com)

### Resource Selectors

Each resource type supports specific selectors:

#### Repository

- `includeArchived`: Include archived repositories (default: false)

#### Pull Request

- `state`: Filter by state - "open", "closed", or "all" (default: "all")

#### Issue

- `state`: Filter by state - "open", "closed", or "all" (default: "all")

#### Team

- `privacy`: Filter by privacy - "secret", "closed", or "all" (default: "all")

#### Workflow

- `state`: Filter by state - "active", "deleted", or "all" (default: "all")

## Architecture

The integration follows the Port Ocean framework patterns:

- **Client Layer**: HTTP client with authentication and pagination
- **Service Layer**: High-level business logic for data fetching
- **Integration Layer**: Resource configuration and webhook handling
- **Webhook Support**: Real-time event processing (planned)

## Development

### Prerequisites

- Python 3.12+
- Poetry for dependency management

### Setup

```bash
cd github-v1/github
poetry install
```

### Running

```bash
poetry run ocean sail
```

## Supported GitHub Resources

- Repositories
- Pull Requests
- Issues
- Teams
- Workflows

## Webhook Events (Planned)

- Repository events (create, delete, archive)
- Pull request events (open, close, merge)
- Issue events (open, close, edit)
- Workflow events (run, complete)
- Team events (create, delete, edit)

## Rate Limiting

The GitHub v1 integration includes comprehensive rate limiting to respect GitHub's API limits and ensure reliable operation.

### GitHub API Rate Limits

GitHub has different rate limits for different types of requests:

- **Core API**: 5,000 requests per hour for authenticated requests
- **Search API**: 30 requests per minute for authenticated requests
- **GraphQL API**: 5,000 points per hour

### Rate Limiting Features

The integration implements several rate limiting strategies:

#### 1. Proactive Rate Limiting

- **Safety Margins**: Uses only 90% of core API limit and 80% of search API limit
- **Request Spacing**: Minimum 100ms between requests
- **API-Specific Limits**: Different limits for core vs search APIs

#### 2. Reactive Rate Limiting

- **Header Monitoring**: Tracks GitHub's rate limit headers in real-time
- **Automatic Backoff**: Waits when approaching rate limits
- **Response Handling**: Automatically handles 429 and 403 responses

#### 3. Smart Retry Logic

- **Exponential Backoff**: Implements exponential backoff for repeated failures
- **Retry-After Headers**: Respects GitHub's retry-after headers
- **Secondary Rate Limits**: Handles abuse detection and secondary limits

### Rate Limit Monitoring

The integration provides visibility into rate limiting:

```python
from github.clients.client_factory import create_github_client

client = create_github_client()

# Get current rate limit status
status = client.get_rate_limit_status()
print(f"Rate limit status: {status}")

# Check GitHub's reported rate limits
github_limits = await client.check_rate_limit()
print(f"GitHub rate limits: {github_limits}")
```

### Rate Limit Configuration

Rate limiting behavior can be customized by modifying the `GitHubRateLimiter` class:

```python
# Example: More conservative rate limiting
CORE_API_SAFETY_MARGIN = 0.2  # Use only 80% of core API limit
SEARCH_API_SAFETY_MARGIN = 0.3  # Use only 70% of search API limit
MIN_REQUEST_INTERVAL = 0.2  # 200ms between requests
```

### Best Practices

1. **Monitor Rate Limits**: Check rate limit status regularly during heavy operations
2. **Batch Operations**: Process data in batches to manage rate limiting effectively
3. **Handle Failures**: Implement proper error handling for rate limit responses
4. **Plan for Limits**: Consider GitHub's rate limits when planning large data operations

### Rate Limit Headers

The integration monitors these GitHub rate limit headers:

- `x-ratelimit-limit`: Maximum requests allowed
- `x-ratelimit-remaining`: Requests remaining in current window
- `x-ratelimit-reset`: When the current window resets
- `x-ratelimit-used`: Requests used in current window
- `retry-after`: Seconds to wait before retrying (on 429 responses)

### Troubleshooting Rate Limits

If you encounter rate limiting issues:

1. **Check Authentication**: Ensure you're using a valid GitHub token
2. **Monitor Usage**: Check your rate limit status and usage patterns
3. **Reduce Concurrency**: Lower the number of concurrent requests
4. **Increase Delays**: Add longer delays between batch operations
5. **Use GitHub Enterprise**: Consider GitHub Enterprise for higher limits

The rate limiter automatically logs important events and rate limit status, making it easy to monitor and troubleshoot rate limiting behavior.

## Running the Integration

### Quick Start

The integration now **automatically loads configuration** from `.env` files! No more manual environment variable setup.

1. **Set up environment**: Copy and configure the environment template:

   ```bash
   cp example.env .env
   # Edit .env with your actual values
   ```

2. **Configure credentials** in your `.env` file:

   - **Port.io**: Set your Port.io client ID and secret
   - **GitHub**: Set your GitHub personal access token

3. **Run the integration**:

   ```bash
   # Run once and exit
   ./run_ocean.sh --once

   # Or run in continuous mode
   ./run_ocean.sh
   ```

4. **Test your configuration** (optional):
   ```bash
   python test_env_config.py
   ```

### Automatic Environment Loading

The integration automatically loads configuration from these files (in order of precedence):

1. `.env` - Main configuration file
2. `.env.local` - Local overrides (gitignored)
3. `config.env` - Alternative configuration file
4. `.env.development` - Development-specific config

**No manual environment variable setup required!** The integration detects and loads your configuration automatically.

### Environment Configuration

The integration requires these environment variables in your `.env` file:

| Variable                                   | Description                      | Required |
| ------------------------------------------ | -------------------------------- | -------- |
| `OCEAN__PORT__CLIENT_ID`                   | Port.io client ID                | ✅       |
| `OCEAN__PORT__CLIENT_SECRET`               | Port.io client secret            | ✅       |
| `OCEAN__PORT__BASE_URL`                    | Port.io API URL                  | ✅       |
| `OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN` | GitHub personal access token     | ✅       |
| `OCEAN__INTEGRATION__CONFIG__GITHUB_HOST`  | GitHub API host (for Enterprise) | ❌       |

### GitHub Token Permissions

Your GitHub personal access token needs these scopes:

- `repo` - Access to repositories (required for private repos)
- `read:org` - Read organization information
- `read:user` - Read user profile information

### Development Mode

For development with more detailed logging, add to your `.env` file:

```bash
OCEAN__LOG_LEVEL=DEBUG
```

### Testing

Test your configuration:

```bash
python test_env_config.py
```

Run the test suite:

```bash
make test
```

Run linting:

```bash
make lint
```

### Troubleshooting

1. **Configuration Errors**: Run `python test_env_config.py` to validate your setup
2. **Missing .env file**: Copy `example.env` to `.env` and fill in your values
3. **Authentication Errors**: Verify your Port.io and GitHub credentials are correct
4. **Import Errors**: Ensure you're running from the correct directory
5. **Rate Limiting**: Check the rate limiting section above for optimization tips

Use `./run_ocean.sh --help` for additional configuration guidance.
