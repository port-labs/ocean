# Jenkins

An integration used to import Jenkins resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/<"link to jenkins integration documentation">/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)


### Modes
This integration operates through two primary processes to extract data from Jenkins and ingest it into Port:

1. Jenkins Jobs Extraction: Retrieves job information from Jenkins.
2. Jenkins Build Extraction: Fetches build data for each job from Jenkins.

Hook Integration: Jenkins triggers an event to the integration whenever a job or build is altered.

For the hook integration, ensure to set the integration hook endpoint in Jenkins. Refer to the instructions [here](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/webhook/examples/jenkins/#create-a-webhook-in-jenkins) to configure Jenkins to utilize the hook. 

### Environment Variables
Configure the integration environment by utilizing the provided `.env.sample` file:

- **.env.sample**: Use this file as a template for setting up the environment variables required for the Jenkins integration. Populate the placeholders with your specific credentials and configurations.

Ensure to create a new file named `.env` and fill it with the necessary values based on the provided `.env.sample`. This configuration file will be used to execute the integration.