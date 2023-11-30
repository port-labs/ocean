# Jenkins

An integration used to import Jenkins resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/<"link to jenkins integration documentation">/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)

#### Data Extraction

This integration utilizes two primary modes to extract data from Jenkins and seamlessly integrate it into Port:

1. Jenkins Jobs Extraction: This mode retrieves detailed information about the jobs configured within Jenkins.
2. Jenkins Build Extraction: This mode fetches comprehensive build data for each job identified in Jenkins.

#### Hook Integration

To ensure real-time synchronization with Jenkins, the integration establishes a hook mechanism. Whenever a job or build undergoes modifications in Jenkins, an event is triggered, notifying the integration of the changes.

#### Configuring the Hook Integration

For the hook integration to function effectively, the integration hook endpoint needs to be configured within Jenkins. Refer to the detailed instructions provided here: https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/webhook/examples/jenkins/#create-a-webhook-in-jenkins to establish the hook connection between Jenkins and the integration.

#### Environment Variables

To configure the integration environment, utilize the provided .env.sample file as a template:

- **.env.sample**: This file serves as a blueprint for setting up the essential environment variables required for the Jenkins integration. Replace the placeholder values with your specific credentials and configurations.

To create the actual configuration file, duplicate the .env.sample file and name it .env. Populate the .env file with the necessary values based on the provided .env.sample. This configuration file will be used to execute the integration seamlessly.