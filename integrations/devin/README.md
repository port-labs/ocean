# Devin

An integration used to import [Devin](https://docs.devin.ai) sessions, playbooks, knowledge notes and secret metadata into Port, and to create, continue, terminate and archive Devin sessions from Port workflows and self-service actions.

Devin has no outbound webhooks, so runs that wait for a session (`reportCompletion: true`) are completed by polling. The integration tags each tracked session and re-discovers its work from those tags on every tick, so restarts don't lose runs. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the reserved tags, the required service-user permissions, and the known limitations.

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.port.io/developing-an-integration/)
