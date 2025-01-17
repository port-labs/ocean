# Contributing to Ocean - hibob

# HiBob Authentication

For integration to work both locally and in production, you need to obtain [HiBob API Service User Credentials](https://apidocs.hibob.com/reference/authorization) and set up [Permissions](https://apidocs.hibob.com/reference/permissions). It is advised to grant the least permissions possible to the API Service User to mitigate any possible data leaks.

## Running locally

1. Fill in .env file values based .env.example using Port Credentials and HiBob API Service User obtained in `Hibob Authentication` section
2. Run the integration: `make run`

# API specification
Currently, API endpoints in use are
- Get Employees' Profiles to ingest `kind=profile`: https://apidocs.hibob.com/reference/get_profiles
- Get Company Lists to ingest `kind=list`: https://apidocs.hibob.com/reference/get_company-named-lists

## Possible next steps

HiBob supports webhooks to update the employees' data in real time: https://apidocs.hibob.com/reference/getting-started-webhooks
