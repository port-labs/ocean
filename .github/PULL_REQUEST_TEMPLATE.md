# Description

What - A new GitHub integration for Port's Ocean framework that syncs GitHub resources to Port.

Why - To allow Port users to import and track their GitHub resources (repositories, pull requests, issues, teams, and workflows) in their developer portal.

How - Using GitHub's REST API v3 with async processing, rate limiting, and webhook support.

## Type of change

Please leave one option from the following and delete the rest:

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] New Integration (non-breaking change which adds a new integration)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Non-breaking change (fix of existing functionality that will not change current behavior)
- [ ] Documentation (added/updated documentation)

<h4> All tests should be run against the port production environment(using a testing org). </h4>

### Core testing checklist

- [ ] Integration able to create all default resources from scratch
- [ ] Resync finishes successfully
- [ ] Resync able to create entities
- [ ] Resync able to update entities
- [ ] Resync able to detect and delete entities
- [ ] Scheduled resync able to abort existing resync and start a new one
- [ ] Tested with at least 2 integrations from scratch
- [ ] Tested with Kafka and Polling event listeners
- [ ] Tested deletion of entities that don't pass the selector


### Integration testing checklist

- [ ] Integration able to create all default resources from scratch
- [ ] Resync able to create entities
- [ ] Resync able to update entities
- [ ] Resync able to detect and delete entities
- [ ] Resync finishes successfully
- [ ] If new resource kind is added or updated in the integration, add example raw data, mapping and expected result to the `examples` folder in the integration directory.
- [ ] If resource kind is updated, run the integration with the example data and check if the expected result is achieved
- [ ] If new resource kind is added or updated, validate that live-events for that resource are working as expected
- [ ] Docs PR link [here](#)

### Preflight checklist

- [ ] Handled rate limiting
- [ ] Handled pagination
- [ ] Implemented the code in async
- [ ] Support Multi account

## Screenshots

Include screenshots from your environment showing how the resources of the integration will look.

Repository Entity:

Pull Request Entity:

Issue Entity:

Team Entity:

Workflow Entity:


## API Documentation

- [GitHub REST API v3](https://docs.github.com/en/rest)
- [Repositories API](https://docs.github.com/en/rest/repos)
- [Pull Requests API](https://docs.github.com/en/rest/pulls)
- [Issues API](https://docs.github.com/en/rest/issues)
- [Teams API](https://docs.github.com/en/rest/teams)
- [Actions (Workflows) API](https://docs.github.com/en/rest/actions)
- [Webhooks API](https://docs.github.com/en/rest/repos/webhooks)

Additional Implementation Details:
1. Rate Limiting:
    - Uses GitHub's rate limit headers (X-RateLimit-)
    - Semaphore for concurrent request limiting
    - Automatic backoff when limits are reached
    - Logging of rate limit status
2. Pagination:
    - Implements GitHub's page-based pagination
    - Configurable page size (default 100)
    - Eficient async processing of pages
    - Proper handling of empty results
3. Webhook Support:
    - Organization-level webhook creation
    - Event-specific processors
    - Secure webhook validation
    - Real-time entity updates
4. Resource Processing:
    - Efficient batch processing
    - Proper error handling
    - Detailed logging
    - Resource relationship mapping