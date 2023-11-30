# Jenkins

Our Jenkins integration allows you to import `jobs` and `builds` from your Jenkins server into Port, according to your mapping and definition.

### Common use cases
Our Jenkins integration makes it easy to fill the software catalog with data directly from your Jenkins server, for example:

- Map all of the jobs and builds in your Jenkins server;
- Watch for Jenkins object changes (create/update/delete) in real-time, and automatically apply the changes to your entities in Port

#### Installation


### Modes
The integration uses two modes to ingest data into Port
1. Resync: Port periodically queries the integrations for jobs and builds data
2. Hook: Jenkins sends an event to the integration every time a job or build is changed.

   - The hook requires that you set the integration hook endpoint in Jenkins
   - Follow the [instructions](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/webhook/examples/jenkins/#create-a-webhook-in-jenkins) here to set up Jenkins to use the hook
   - The hook url will be {integration_url_host}/integration/events e.g. http://localhost:8000/integration/events

### Environment Variables
Set the following variables in your environment before running the integration

```bash
PORT_CLIENT_ID={{PORT_CLIENT_ID}}
PORT_CLIENT_SECRET={{PORT_CLIENT_SECRET}}
INTEGRATION_IDENTIFIER=jenkins
JENKINS_HOST=http://localhost:8080
JENKINS_USER={{JENKINS_USER}}
JENKINS_PASSWORD={{JENKINS_PASSWORD}}
```

