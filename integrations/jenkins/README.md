# Jenkins

An integration used to import Jenkins resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/) *Replace this link with a link to this integration's documentation*

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)


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

